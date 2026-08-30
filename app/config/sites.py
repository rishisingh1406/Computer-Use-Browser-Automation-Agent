from dataclasses import dataclass


@dataclass(frozen=True)
class LoginConfig:
    username_selector: str
    password_selector: str
    submit_selector: str
    username_env: str
    password_env: str



SITE_CONFIGS = {
    "site2": LoginConfig(
        username_selector='input[name="username"]',
        password_selector='input[name="password"]',
        submit_selector='button[type="submit"]',
        username_env="SITE2_USERNAME",
        password_env="SITE2_PASSWORD",
    ),

    "site3": LoginConfig(
        username_selector='input[name="email"]',
        password_selector='input[name="password"]',
        submit_selector='button[type="submit"]',
        username_env="SITE3_USERNAME",
        password_env="SITE3_PASSWORD",
    ),
}