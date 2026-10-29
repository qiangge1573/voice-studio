"""应用配置：全部从环境变量读取，未设置时使用默认值。"""
import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass
class Settings:
    engine: str = field(default_factory=lambda: _env("ENGINE", "mock"))
    wechat_app_id: str = field(default_factory=lambda: _env("WECHAT_APP_ID", ""))
    wechat_app_secret: str = field(default_factory=lambda: _env("WECHAT_APP_SECRET", ""))
    host: str = field(default_factory=lambda: _env("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(_env("PORT", "8000")))
    data_dir: str = field(default_factory=lambda: _env("DATA_DIR", "./data"))
    jwt_secret: str = field(
        default_factory=lambda: _env("JWT_SECRET", "dev-secret-change-me")
    )
    device: str = field(default_factory=lambda: _env("DEVICE", "cpu"))
    cosyvoice_model_dir: str = field(
        default_factory=lambda: _env("COSYVOICE_MODEL_DIR", "pretrained_models/CosyVoice2-0.5B")
    )
    volc_api_key: str = field(default_factory=lambda: _env("VOLC_API_KEY", ""))
    max_upload_mb: int = 10

    @property
    def dev_mode(self) -> bool:
        """未配置有效 AppID 时进入开发模式：登录接口接受 code=dev。"""
        return not self.wechat_app_id or self.wechat_app_id in ("wx0000000000000000",)

    @property
    def samples_dir(self) -> str:
        return os.path.join(self.data_dir, "samples")

    @property
    def outputs_dir(self) -> str:
        return os.path.join(self.data_dir, "outputs")

    @property
    def videos_dir(self) -> str:
        return os.path.join(self.data_dir, "videos")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "voice_studio.db")
