"""
이메일 발송 진단 스크립트 - 여러 SMTP 서버 자동 시도
실행: py test_email.py
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import dotenv_values
import os

cfg    = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
user   = cfg.get("EMAIL_USER", "")
passwd = cfg.get("EMAIL_PASS", "")
to_    = cfg.get("EMAIL_TO", "")

# 시도할 SMTP 서버 목록 (순서대로 시도)
SMTP_CANDIDATES = [
    ("smtp.office365.com",  587,  "Microsoft 365"),
    ("smtp.stic.co.kr",     587,  "stic 자체 서버 (587)"),
    ("smtp.stic.co.kr",     465,  "stic 자체 서버 (465/SSL)"),
    ("mail.stic.co.kr",     587,  "stic mail 서버"),
    ("smtp.gmail.com",      587,  "Gmail (참고용)"),
]

print("=" * 55)
print("  이메일 발송 진단")
print(f"  발신/수신: {user}")
print("=" * 55)

def try_send(smtp_server, port, label):
    msg = MIMEMultipart()
    msg["Subject"] = f"✅ 주식 스크리닝 — 이메일 테스트 [{label}]"
    msg["From"]    = user
    msg["To"]      = to_
    msg.attach(MIMEText(f"SMTP 서버 [{label}] 로 발송 성공!", "plain", "utf-8"))

    try:
        if port == 465:
            import ssl
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, port, context=ctx, timeout=10) as srv:
                srv.login(user, passwd)
                srv.sendmail(user, to_, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, port, timeout=10) as srv:
                srv.ehlo()
                srv.starttls()
                srv.ehlo()
                srv.login(user, passwd)
                srv.sendmail(user, to_, msg.as_string())
        return True, "성공"
    except smtplib.SMTPAuthenticationError:
        return False, "❌ 인증 실패 (비밀번호 오류 또는 SMTP 비활성화)"
    except smtplib.SMTPConnectError as e:
        return False, f"❌ 연결 실패 ({e})"
    except ConnectionRefusedError:
        return False, "❌ 연결 거부 (포트 닫힘)"
    except TimeoutError:
        return False, "❌ 타임아웃 (서버 없음)"
    except Exception as e:
        return False, f"❌ {type(e).__name__}: {e}"

success = False
for smtp_server, port, label in SMTP_CANDIDATES:
    print(f"\n  시도: {label} ({smtp_server}:{port})")
    ok, msg = try_send(smtp_server, port, label)
    print(f"  결과: {'✅ 발송 성공!' if ok else msg}")
    if ok:
        success = True
        # .env에 성공한 서버로 자동 업데이트
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        content  = open(env_path).read()
        old_line = [l for l in content.splitlines() if l.startswith("SMTP_SERVER=")]
        if old_line:
            content = content.replace(old_line[0], f"SMTP_SERVER={smtp_server}")
            old_port = [l for l in content.splitlines() if l.startswith("SMTP_PORT=")]
            if old_port:
                content = content.replace(old_port[0], f"SMTP_PORT={port}")
            open(env_path, "w").write(content)
            print(f"  → .env 자동 업데이트 완료 ({smtp_server}:{port})")
        break

print("\n" + "=" * 55)
if success:
    print("  ✅ 발송 성공! 받은편지함(또는 스팸함)을 확인하세요.")
else:
    print("  ❌ 모든 서버에서 실패했습니다.")
    print()
    print("  해결 방법:")
    print("  1. 회사 IT팀에 'SMTP 서버 주소와 포트' 문의")
    print("  2. 또는 Gmail 계정을 발신용으로 사용:")
    print("     .env에서 아래와 같이 수정:")
    print("       SMTP_SERVER=smtp.gmail.com")
    print("       EMAIL_USER=본인Gmail@gmail.com")
    print("       EMAIL_PASS=Gmail앱비밀번호16자리")
    print("       EMAIL_FROM=본인Gmail@gmail.com")
    print("       EMAIL_TO=geunho@stic.co.kr")
print("=" * 55)
