"""仅用于小规模演示的预设账号；不包含注册和找回密码。"""
import getpass
import hashlib
import hmac
import secrets


def make_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200000)
    return salt + ":" + digest.hex()


def verify(password, saved):
    try:
        salt, expected = saved.split(":")
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 200000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


if __name__ == "__main__":
    password = getpass.getpass("输入新密码（输入时不显示）：")
    again = getpass.getpass("再输入一次：")
    if password != again or len(password) < 10:
        raise SystemExit("两次密码须相同且至少10个字符，请重新运行")
    print("把下面整行复制到 secrets.toml 对应账号的引号内：")
    print(make_hash(password))
