# 공지사항 PowerPoint 첨부

## 사용 방법

관리자 로그인 → 홈 공지사항의 **더보기** → **공지 작성** → 제목·내용과 **PowerPoint 파일 선택** → **저장**.

- 지원: `.ppt`, `.pptx`, 공지당 파일 1개, 최대 20MB.
- 로그인한 학생은 공지 상세의 **다운로드** 버튼으로 자료를 받는다. 웹 슬라이드 미리보기는 제공하지 않는다.
- 수정 화면에서 새 파일을 고르면 교체한다. **현재 첨부파일 삭제**를 선택하고 저장하면 파일만 삭제한다.
- 파일 없이도 기존처럼 공지를 작성할 수 있다. 일반 학생은 공지 작성·수정·삭제 권한이 없다.

## 저장 구조와 유지보수

- 기존 `notices` 테이블은 유지하고 신규 `notice_attachments` 테이블에 원본 이름·임의 저장명·크기·공지 연결을 저장한다.
- 파일 경로 기본값은 `<프로젝트>/instance/notice-attachments/`. 운영에서는 `/var/www/voca_app/instance/notice-attachments/`이며 `NOTICE_UPLOAD_DIR` 환경변수로 변경할 수 있다.
- 저장 경로는 `static/` 밖이다. 로그인한 사용자에게 `/notices/<공지ID>/attachment`로 다운로드를 제공한다.
- 공지 쓰기/수정/삭제에는 관리 권한과 CSRF 토큰 검증을 적용한다.
- PPT는 OLE PowerPoint 스트림을 검사하고, PPTX는 ZIP 구조·주요 XML·CRC·압축 크기를 검사한다. 확장자만 바꾼 파일은 거절한다. 파일을 실행하거나 서버에서 Office로 변환하지 않는다.
- 임의 저장명, 응답의 `attachment`, `nosniff`, `private, no-store`를 적용한다. 이 검사는 파일 구조 검사이며 악성코드 백신 검사를 의미하지 않는다.
- 신규 파일 저장/DB 커밋 실패 시 새 파일을 정리한다. 교체/삭제는 DB 커밋 후 이전 파일을 정리한다.
- 새 의존성은 `olefile==0.47`. 나머지 Flask·DB 의존성은 기존 구성을 사용한다.

## 배포·백업

1. 현재 코드·DB·Nginx 설정과 `instance/notice-attachments/`를 백업한다.
2. 요구 패키지 설치, 변경 코드와 템플릿·CSS를 반영한다. 운영 환경의 DB 설정을 사용하는 셸에서 `python scripts/init_notice_attachments.py`로 새 메타데이터 테이블을 준비한다.
3. 기존 HTTPS server 블록 안에 `deploy/nginx-notices.conf` 내용을 include한다. 경로형 Moodle include와 기존 프록시는 유지한다. Nginx는 공지 경로에만 21MB 요청 한도를 적용하고, Flask는 실제 파일 20MB를 검증한다.
4. `nginx -t` 성공 후 reload하고 Gunicorn worker를 순차 reload한다. 기존 공지, 첨부 업로드/다운로드, 학생 권한을 확인한다.

DB만 백업하면 파일이 복구되지 않는다. **DB + 첨부 디렉터리 + 코드**를 같은 시점 기준으로 보관한다. Git에는 첨부 디렉터리를 올리지 않는다.

코드 롤백은 백업된 변경 파일·Nginx 설정을 복원하고 Gunicorn/Nginx를 reload한다. 추가된 테이블·첨부 디렉터리는 보존한다. 실제 게시물이 생긴 뒤 DB를 과거 백업으로 덮어쓰거나 테이블을 삭제하면 새 자료를 잃을 수 있다.

## 검사

```bash
python -m unittest discover -s tests -p 'test_notice_attachments.py' -v
```

15개 검사는 관리자 업로드·학생 다운로드·로그인/권한·CSRF·한글 파일명·XSS·확장자/ZIP/용량 검증·교체/삭제·DB 실패 시 원본 보존을 다룬다.
