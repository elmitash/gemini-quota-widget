from __future__ import annotations

import glob
import json
import re
import subprocess
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ_PT = ZoneInfo("America/Los_Angeles")
TZ_KST = ZoneInfo("Asia/Seoul")


@dataclass
class BucketMetric:
    name: str
    remaining_pct: float  # 0.0 ~ 100.0 (%)
    used_pct: float
    description: str
    reset_time_str: str  # ISO string
    remaining_time_str: str  # HH:MM:SS or Xd Yh
    next_reset_kst_str: str  # e.g., "15:16 KST" or "09-18 07:38 KST"


@dataclass
class QuotaSummaryData:
    group_name: str
    weekly: BucketMetric
    short_term: BucketMetric  # 5h (Daily/Session)
    account_tier: str
    account_email: str
    is_live_rpc: bool


class QuotaTracker:
    """Antigravity LanguageServerService/RetrieveUserQuotaSummary RPC를 호출하여

    구글 공식 Model Quota UI와 100% 동일한 주간(Weekly) 및 단기(5-Hour) 전역 한도 데이터를 추적합니다.
    """

    DEFAULT_CONFIG = {
        "always_on_top": True,
        "window_x": 120,
        "window_y": 80,
        "poll_interval_seconds": 15,
        "target_group": "Gemini Models",  # "Gemini Models" 또는 "Claude and GPT models"
    }

    def __init__(self, config_path: str | Path = "config.json") -> None:
        self.config_path = Path(config_path)
        self.config: dict = {}
        self.cached_port: int | None = None
        self.cached_token: str | None = None
        self.last_quota_summary: dict | None = None
        self.user_tier: str = "Pro"
        self.user_email: str = ""
        self.is_fetching = False

        self.load_config()
        self.fetch_quota_summary()

    def load_config(self) -> None:
        if not self.config_path.exists():
            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = {**self.DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self) -> None:
        try:
            temp_file = self.config_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            temp_file.replace(self.config_path)
        except OSError as e:
            print(f"[QuotaTracker] 설정 저장 실패: {e}")

    def discover_connection(self) -> tuple[int | None, str | None]:
        """실행 중인 Antigravity language_server의 로컬 포트와 CSRF 토큰을 자동 탐색합니다."""
        if self.cached_port and self.cached_token:
            if self._test_rpc(self.cached_port, self.cached_token):
                return self.cached_port, self.cached_token

        for p in glob.glob("/proc/[0-9]*/cmdline"):
            try:
                with open(p, "rb") as f:
                    args = f.read().split(b"\0")
                args_str = [a.decode("latin1", errors="ignore") for a in args]
                if any("language_server" in a for a in args_str) and "--csrf_token" in args_str:
                    pid = p.split("/")[2]
                    idx = args_str.index("--csrf_token")
                    csrf_token = args_str[idx + 1] if idx + 1 < len(args_str) else None
                    if not csrf_token:
                        continue

                    out = subprocess.check_output(["ss", "-tlpn"], text=True)
                    ports = []
                    for line in out.splitlines():
                        if f"pid={pid}," in line:
                            m_port = re.search(r"127\.0\.0\.1:(\d+)", line)
                            if m_port:
                                ports.append(int(m_port.group(1)))

                    for port in ports:
                        if self._test_rpc(port, csrf_token):
                            self.cached_port = port
                            self.cached_token = csrf_token
                            return port, csrf_token
            except Exception:
                continue

        return None, None

    def _test_rpc(self, port: int, token: str) -> bool:
        try:
            url = f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
            req = urllib.request.Request(
                url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Codeium-Csrf-Token": token,
                    "Connect-Protocol-Version": "1",
                },
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                if "response" in data and "groups" in data["response"]:
                    return True
        except Exception:
            pass
        return False

    def fetch_quota_summary(self) -> dict | None:
        """language_server RPC(RetrieveUserQuotaSummary)를 호출하여 주간/5시간 쿼터 데이터를 수신합니다."""
        port, token = self.discover_connection()
        if not port or not token:
            return self.last_quota_summary

        try:
            url = f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
            req = urllib.request.Request(
                url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Codeium-Csrf-Token": token,
                    "Connect-Protocol-Version": "1",
                },
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode())
                if "response" in data and "groups" in data["response"]:
                    self.last_quota_summary = data["response"]

            # 계정 티어 및 이메일 동적 확인 (선택적)
            try:
                url_status = f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUserStatus"
                req_status = urllib.request.Request(
                    url_status,
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "X-Codeium-Csrf-Token": token,
                        "Connect-Protocol-Version": "1",
                    },
                )
                with urllib.request.urlopen(req_status, timeout=1.5) as resp_s:
                    data_s = json.loads(resp_s.read().decode())
                    ustatus = data_s.get("userStatus", {})
                    self.user_email = ustatus.get("email", "")
                    tier_info = ustatus.get("userTier", {})
                    if isinstance(tier_info, dict) and tier_info.get("name"):
                        self.user_tier = "Pro" if "pro" in tier_info.get("name", "").lower() else tier_info.get("name")
                    elif ustatus.get("planStatus", {}).get("planInfo", {}).get("planName"):
                        self.user_tier = ustatus["planStatus"]["planInfo"]["planName"]
            except Exception:
                pass

            return self.last_quota_summary
        except Exception as e:
            print(f"[QuotaTracker] RetrieveUserQuotaSummary 호출 실패: {e}")

        return self.last_quota_summary

    def trigger_rpc_async(self, callback=None) -> None:
        """백그라운드 비동기 RPC 호출."""
        if self.is_fetching:
            return

        def _worker():
            self.is_fetching = True
            try:
                self.fetch_quota_summary()
            finally:
                self.is_fetching = False
                if callback:
                    callback()

        threading.Thread(target=_worker, daemon=True).start()

    def _parse_time_diff(self, reset_time_str: str) -> tuple[str, str]:
        """ISO 타임스탬프로부터 남은 시간 문자열과 KST 포맷을 계산합니다."""
        if not reset_time_str:
            return "00:00:00", ""

        try:
            clean_ts = reset_time_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            now_utc = datetime.now(timezone.utc)

            diff_sec = max(0, int((dt - now_utc).total_seconds()))
            days, rem = divmod(diff_sec, 86400)
            hours, rem = divmod(rem, 3600)
            mins, secs = divmod(rem, 60)

            if days > 0:
                time_left = f"{days}d {hours}h {mins}m"
            else:
                time_left = f"{hours:02d}:{mins:02d}:{secs:02d}"

            kst_dt = dt.astimezone(TZ_KST)
            kst_str = kst_dt.strftime("%m-%d %H:%M KST") if days > 0 else kst_dt.strftime("%H:%M KST")
            return time_left, kst_str
        except Exception:
            return "00:00:00", ""

    def get_quota_summary_data(self) -> QuotaSummaryData:
        """공식 UI 규격의 주간 및 5시간 버킷 데이터를 완벽히 파싱하여 반환합니다."""
        data = self.last_quota_summary or {}
        groups = data.get("groups", [])
        target_name = self.config.get("target_group", "Gemini Models")

        selected_group = None
        for g in groups:
            if target_name.lower() in g.get("displayName", "").lower():
                selected_group = g
                break
        if not selected_group and groups:
            selected_group = groups[0]

        weekly_metric = BucketMetric(
            name="Weekly Limit Remaining",
            remaining_pct=100.0,
            used_pct=0.0,
            description="Fully refreshed",
            reset_time_str="",
            remaining_time_str="00:00:00",
            next_reset_kst_str="",
        )

        short_metric = BucketMetric(
            name="Five Hour Limit Remaining",
            remaining_pct=100.0,
            used_pct=0.0,
            description="Fully refreshed",
            reset_time_str="",
            remaining_time_str="00:00:00",
            next_reset_kst_str="",
        )

        group_display = "Gemini Models"
        if selected_group:
            group_display = selected_group.get("displayName", group_display)
            for b in selected_group.get("buckets", []):
                window = b.get("window", "")
                frac = float(b.get("remainingFraction", 1.0))
                rem_pct = round(frac * 100.0, 1)
                used_pct = round((1.0 - frac) * 100.0, 1)
                desc = b.get("description", "")
                reset_ts = b.get("resetTime", "")
                t_left, kst_str = self._parse_time_diff(reset_ts)

                metric = BucketMetric(
                    name=b.get("displayName", window),
                    remaining_pct=rem_pct,
                    used_pct=used_pct,
                    description=desc,
                    reset_time_str=reset_ts,
                    remaining_time_str=t_left,
                    next_reset_kst_str=kst_str,
                )

                if window == "weekly" or "weekly" in b.get("bucketId", ""):
                    weekly_metric = metric
                elif window == "5h" or "5h" in b.get("bucketId", ""):
                    short_metric = metric

        return QuotaSummaryData(
            group_name=group_display,
            weekly=weekly_metric,
            short_term=short_metric,
            account_tier=self.user_tier,
            account_email=self.user_email,
            is_live_rpc=bool(self.last_quota_summary),
        )

    def update_window_position(self, x: int, y: int) -> None:
        self.config["window_x"] = x
        self.config["window_y"] = y
        self.save_config()

    def set_always_on_top(self, enabled: bool) -> None:
        self.config["always_on_top"] = enabled
        self.save_config()
