"""One persistent site password and revocable, process-local browser sessions."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import deque
from http.cookies import CookieError, SimpleCookie
from pathlib import Path

from .registry import Registry
from .store import FreezeError, atomic_json, ordinary_file

ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60
ATTEMPT_WINDOW = 5 * 60


class AuthError(FreezeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class SiteAuth:
    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / ".auth/password.json"
        self.cookie_name = "council_" + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]
        self.lock = threading.RLock()
        self.sessions: dict[str, float] = {}
        self.attempts: deque[tuple[float, str]] = deque()
        self.record = self.read()

    def read(self) -> dict | None:
        if self.directory.is_symlink() or self.path.parent.is_symlink():
            raise FreezeError("Site password directory must not be linked")
        raw = ordinary_file(self.path, 4096)
        if raw is None:
            return None
        try:
            record = json.loads(raw)
            if (record["schema_version"] != 1 or record["algorithm"] != "pbkdf2-sha256"
                    or record["iterations"] != ITERATIONS
                    or len(bytes.fromhex(record["salt"])) != 32
                    or len(bytes.fromhex(record["hash"])) != 32):
                raise ValueError
        except (ValueError, KeyError, TypeError) as error:
            raise FreezeError("Site password file is invalid; refusing to open the site") from error
        return record

    @staticmethod
    def password(value) -> bytes:
        if not isinstance(value, str) or not 8 <= len(value) <= 128 or not value.strip() or "\x00" in value:
            raise AuthError("密码需为 8–128 个字符，不能全为空格。")
        try:
            return value.encode("utf-8")
        except UnicodeError as error:
            raise AuthError("密码包含无效字符，请重新输入。") from error

    def rate_limit(self, peer: str):
        now = time.monotonic()
        while self.attempts and self.attempts[0][0] <= now - ATTEMPT_WINDOW:
            self.attempts.popleft()
        if len(self.attempts) >= 60 or sum(ip == peer for _, ip in self.attempts) >= 10:
            raise AuthError("尝试过于频繁，请 5 分钟后再试。", 429)
        self.attempts.append((now, peer))

    def enter(self, password, peer: str, *, setup=False, confirmation=None) -> str:
        with self.lock:
            self.rate_limit(peer)
            if setup:
                raw = self.password(password)
                if password != confirmation:
                    raise AuthError("两次输入的密码不一致。")
                with Registry(self.directory).locked():
                    self.record = self.read()
                    if self.record is not None:
                        raise AuthError("本站已设置密码，请使用现有密码登录。", 409)
                    self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    os.chmod(self.path.parent, 0o700)
                    salt = secrets.token_bytes(32)
                    record = {"schema_version": 1, "algorithm": "pbkdf2-sha256",
                              "iterations": ITERATIONS, "salt": salt.hex(),
                              "hash": hashlib.pbkdf2_hmac("sha256", raw, salt, ITERATIONS).hex()}
                    atomic_json(self.path, record)
                    self.record = record
            else:
                if self.record is None:
                    raise AuthError("本站尚未设置密码，请先完成设置。", 409)
                raw = self.password(password)
                actual = hashlib.pbkdf2_hmac("sha256", raw, bytes.fromhex(self.record["salt"]), ITERATIONS)
                if not hmac.compare_digest(actual.hex(), self.record["hash"]):
                    raise AuthError("密码不正确，请重试。", 403)
            now = time.monotonic()
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 1024:
                del self.sessions[min(self.sessions, key=self.sessions.get)]
            token = secrets.token_urlsafe(32)
            self.sessions[self.digest(token)] = now + SESSION_SECONDS
            return token

    @staticmethod
    def digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def token(self, header: str) -> str:
        try:
            cookies = SimpleCookie(header)
            value = cookies.get(self.cookie_name)
            return value.value if value else ""
        except CookieError:
            return ""

    def authenticated(self, header: str) -> bool:
        with self.lock:
            key = self.digest(self.token(header))
            expiry = self.sessions.get(key, 0)
            if expiry <= time.monotonic():
                self.sessions.pop(key, None)
                return False
            return self.record is not None

    def logout(self, header: str):
        with self.lock:
            self.sessions.pop(self.digest(self.token(header)), None)

    def cookie(self, token: str, secure: bool = False) -> str:
        age = SESSION_SECONDS if token else 0
        return (f"{self.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}"
                + ("; Secure" if secure else ""))
