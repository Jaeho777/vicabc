# 공지사항 PowerPoint 첨부

## 사용 방법

관리자 로그인 → 홈 공지사항의 **더보기** → **공지 작성** → 제목·내용과 **PowerPoint 파일 선택** → **저장**.

- 지원: `.ppt`, `.pptx`, 공지당 파일 1개, 최대 20MB.
- 로그인한 학생은 공지 상세의 **iframe 슬라이드 미리보기**로 바로 읽는다. **이전·다음**, 키보드 방향키·Home·End, **전체 화면**을 지원한다. **별도 창에서 보기**와 **원본 다운로드**도 유지한다.
- 최초 열람 시 서버에서 한 번 변환한다. 이후에는 저장된 이미지로 보여준다. 기존 첨부파일도 처음 열 때 같은 방식으로 처리한다.
- 미리보기는 최대 100장, 긴 변환은 75초 제한이다. 애니메이션·동영상·음성·발표자 노트는 지원하지 않는 정적 보기다. 설치되지 않은 원본 글꼴은 대체되므로 일부 배치가 달라질 수 있다. 변환 실패 시 원본 다운로드는 계속 가능하다.
- 수정 화면에서 새 파일을 고르면 교체한다. **현재 첨부파일 삭제**를 선택하고 저장하면 파일만 삭제한다.
- 파일 없이도 기존처럼 공지를 작성할 수 있다. 일반 학생은 공지 작성·수정·삭제 권한이 없다.

## 저장 구조와 유지보수

- 기존 `notices` 테이블은 유지하고 신규 `notice_attachments` 테이블에 원본 이름·임의 저장명·크기·공지 연결을 저장한다.
- 파일 경로 기본값은 `<프로젝트>/instance/notice-attachments/`. 운영에서는 `/var/www/voca_app/instance/notice-attachments/`이며 `NOTICE_UPLOAD_DIR` 환경변수로 변경할 수 있다.
- 저장 경로는 `static/` 밖이다. 로그인한 사용자에게 `/notices/<공지ID>/attachment`로 다운로드를 제공한다.
- 공지 쓰기/수정/삭제에는 관리 권한과 CSRF 토큰 검증을 적용한다.
- PPT는 OLE PowerPoint 스트림을 검사하고, PPTX는 ZIP 구조·주요 XML·CRC·압축 크기를 검사한다. 확장자만 바꾼 파일은 거절한다.
- 미리보기는 서버의 **LibreOffice → PDF → Poppler PNG**로 생성한다. Microsoft·Google 등 외부 문서 뷰어로 원본을 보내지 않는다. 원본·변환 이미지는 정적 공개 폴더가 아니며 로그인한 사용자만 접근한다. 기존 공지와 같은 열람 범위로, 반별 권한 분리는 이번 기능에 포함하지 않는다.
- 임의 저장명, 응답의 `attachment`, `nosniff`, `private, no-store`를 적용한다. 이 검사는 파일 구조 검사이며 악성코드 백신 검사를 의미하지 않는다.
- 신규 파일 저장/DB 커밋 실패 시 새 파일을 정리한다. 교체/삭제는 DB 커밋 후 이전 파일을 정리한다.
- Python 의존성은 기존 `olefile==0.47`을 유지한다. 변환에는 무료 OS 패키지 `libreoffice-impress`, `poppler-utils`, `fonts-nanum`을 추가한다. 새 DB 테이블·칼럼은 필요하지 않다.

## 미리보기 보안·운영

- `app/services/notice_preview.py`: 상태·캐시·전역 변환 잠금·출력 검증. `scripts/render_notice_preview.py`: Flask·DB·비밀값을 불러오지 않는 변환 전용 실행 파일.
- 운영 웹 프로세스의 기존 root 실행 환경에서 systemd 일회성 작업을 시작하되, **문서 변환 자체는 비권한 `vicpreview` 사용자**로 실행한다. 비root 웹 프로세스로 이전하면 이 실행 연계를 별도 작업 서비스로 분리해야 한다. 동작시키려고 웹 사용자에게 무제한 sudo 권한을 주면 안 된다.
- 작업은 네트워크 차단, 파일시스템 읽기 전용, 웹 코드·운영 백업 접근 차단, 다른 사용자의 프로세스 정보 차단, 권한 상승 금지로 격리한다. 메모리 1GB·CPU 1코어 상당·작업 75초·동시 변환 1개로 제한한다. 임시 작업 영역은 용량 제한 tmpfs이고 매크로 보안 수준은 최대로 설정한다. 이는 백신 검사나 완전한 가상머신 격리를 의미하지 않는다. OS 보안 업데이트가 필요하다.
- 변환 결과는 검증된 평면 PNG와 메타데이터만 채택한다. 파일별 최대 변 1600px·8MB, 전체 캐시 최대 200MB다. 경로 탐색·심볼릭 링크·중복 항목은 거절한다.
- 기본 캐시: `instance/notice-previews/<임의저장명>/`. root 전용으로 저장하며 `NOTICE_PREVIEW_DIR` 환경변수로 변경 가능하다. 첨부 교체·삭제 후 관련 캐시를 삭제한다. 변환 오류는 60초간 재시도 횟수를 제한한다. 동시 변환 중인 다른 요청은 잠시 기다린 뒤 재시도한다.
- `GET /notices/<ID>/preview`: 상태 조회만. `POST .../preview/prepare`: 로그인+세션 CSRF 검증 후 변환. `GET .../preview/pages/<페이지>`: 현재 첨부의 PNG만 제공한다. 모두 `private, no-store`, `nosniff`를 적용한다.
- `GET .../preview/viewer`: 같은 사이트의 독립 HTML 뷰어다. iframe에 PPT 원본 URL을 직접 넣거나 외부 Office 뷰어에 파일을 공개하지 않는다. 본문과 뷰어의 CSS·문서 구조를 분리하며, 뷰어에는 외부 CDN을 사용하지 않는다. `SAMEORIGIN`, CSP `frame-ancestors 'self'`, 로그인 검증으로 같은 사이트 안에서만 프레임 표시를 허용한다. 모바일 브라우저가 전체 화면을 제한하면 **별도 창에서 보기**를 사용한다.
- `NOTICE_PREVIEW_ENABLED=0`으로 새 변환을 중지할 수 있다. 이미 생성된 캐시는 계속 열람할 수 있다. 원본 다운로드와 공지 기능에는 영향이 없다.

## 배포·백업

1. 현재 코드·DB·Nginx 설정과 `instance/notice-attachments/`를 백업한다.
2. 요구 패키지 설치, 변경 코드와 템플릿·CSS를 반영한다. 운영 환경의 DB 설정을 사용하는 셸에서 `python scripts/init_notice_attachments.py`로 새 메타데이터 테이블을 준비한다.
3. 기존 HTTPS server 블록 안에 `deploy/nginx-notices.conf` 내용을 include한다. 경로형 Moodle include와 기존 프록시는 유지한다. Nginx는 공지 경로에만 21MB 요청 한도를 적용하고, Flask는 실제 파일 20MB를 검증한다.
4. `nginx -t` 성공 후 Nginx를 reload하고 아래 운영 주의사항에 따라 앱 서비스를 교체한다. 기존 공지, 첨부 업로드/다운로드, 학생 권한을 확인한다.

### 웹 미리보기 설치 추가 절차

운영 확인 환경은 Ubuntu 22.04·systemd 249·LibreOffice 7.3.7·Poppler 22.02이며, LibreOffice/Poppler는 Ubuntu 보안 저장소 패키지를 사용한다.

1. 신뢰하는 체크아웃에서 root로 `bash deploy/install-notice-preview.sh`를 실행한다. 전용 비로그인 계정, root 소유 작업 경로, `/opt/vicabc-preview/render_notice_preview.py`를 준비한다. 이 스크립트는 앱·DB·Nginx를 재시작하지 않는다.
2. 앱의 preview 서비스·라우트·첨부 정리 훅·템플릿·CSS·JS를 함께 배포한다. 렌더러 스크립트를 수정했다면 `/opt/vicabc-preview/`에도 다시 설치한다.
3. Nginx 공지 location의 `proxy_read_timeout 100s`와 **정확한 `/notices` location**을 함께 적용한다. prefix `/notices/`만 설정하면 Nginx가 목록 주소에 슬래시를 붙일 수 있다. 앱에서도 목록 양쪽 주소를 허용한다. Gunicorn timeout도 변환 상한보다 길어야 한다(현재 운영값 300초). Nginx 검사 후 reload, Gunicorn worker를 교체한다. 운영 Gunicorn master의 HUP 시 로깅 재진입 오류가 관찰되어 이번 수정에서는 `systemctl restart voca_app`으로 교체한다(잠시 연결 중단 가능).
4. 실제 한글 PPTX로 업로드→학생 로그인→자동 변환→여러 장 넘기기→전체 화면→모바일을 확인한다. 익명 이미지 접근, CSRF 누락, 첨부 교체 후 이전 이미지 접근은 차단되어야 한다.

캐시는 원본으로 재생성하므로 백업 필수 항목이 아니다. **원본 첨부+DB+코드**를 반드시 보관한다. 이번 미리보기 코드 롤백은 이전 코드와 Nginx 공지 설정을 복원한 뒤 reload하며, 원본·DB는 그대로 둔다. 추가한 OS 패키지나 전용 계정을 강제로 삭제할 필요는 없다.

DB만 백업하면 파일이 복구되지 않는다. **DB + 첨부 디렉터리 + 코드**를 같은 시점 기준으로 보관한다. Git에는 첨부 디렉터리를 올리지 않는다.

코드 롤백은 백업된 변경 파일·Nginx 설정을 복원하고 Gunicorn/Nginx를 reload한다. 추가된 테이블·첨부 디렉터리는 보존한다. 실제 게시물이 생긴 뒤 DB를 과거 백업으로 덮어쓰거나 테이블을 삭제하면 새 자료를 잃을 수 있다.

## 검사

```bash
python -m unittest discover -s tests -v
```

70개 검사는 업로드·다운로드 회귀와 함께 로그인/CSRF, 목록 URL 양쪽 형식, iframe·CSP·별도 창 링크, 슬라이드 응답, 캐시 무결성, PNG·용량·페이지 제한, 경로/링크 차단, 변환 잠금·타임아웃·정리, 첨부 교체/삭제 연동을 다룬다. 단위 테스트는 임시 SQLite/파일을 사용하며 실제 서버의 문서 변환·시각 검사는 별도로 수행한다.

### 운영 확인 — 2026-10-15

`https://www.vicabc.kr` 공개 HTTPS 주소에서 관리자 업로드, 1MB를 넘는 실제 PPTX, 한글 파일명, 학생의 바이트 일치 다운로드, 익명/학생 권한 제한, 파일 교체·삭제를 확인했다. 검증용 공지는 삭제했고 기존 공지·학생 계정은 보존했다. 영어 사이트와 Moodle 모두 정상 응답을 확인했다.

운영 코드·MySQL DB·Nginx 변경 전 백업은 서버의 `/opt/vicabc-backups/notice-ppt-20261015-050127/`에 root 전용으로 보관한다. 백업에는 개인정보가 있으므로 GitHub에 포함하지 않는다.

### 웹 미리보기 운영 확인 — 2026-10-16

- 자동 검사 57개를 로컬 Python 3.13과 운영 서버 Python 3.10의 분리된 테스트 환경에서 통과했다.
- 공개 HTTPS 사이트에서 관리자 한글 PPTX 업로드 → 일반 학생 로그인 → 3장 자동 변환 → PNG 열람 → 원본 다운로드 일치를 확인했다. 예시 파일의 최초 변환은 약 2.1초였으며 실제 파일에 따라 달라진다.
- 실제 Chrome에서 1440px PC·390px 모바일 화면 크기, 이전/다음·키보드·전체 화면을 확인했다. 다운로드 발생과 JavaScript 오류는 없었다. 변환된 한글 화면을 이미지로도 점검했다.
- 익명 접근 차단, CSRF 누락 차단, 잘못된 페이지 번호 차단, 첨부 교체 시 이전 이미지 미노출을 확인했다. 서버의 실제 구형 `.ppt`도 3장 변환에 성공했다.
- 검증 공지는 삭제했고 관련 첨부·캐시·변환 작업은 정리되었다. 기존 공지·학생 계정과 Moodle은 유지했다. 영어 사이트와 Moodle 로그인 화면은 HTTP 200으로 확인했다.
- 미리보기 변경 전 코드·첨부·Nginx 공지 설정 백업 및 배포 패키지는 `/opt/vicabc-backups/notice-preview-20261016-nQXWGJ/`에 root 전용 보관한다. 이번 기능은 운영 DB 스키마를 변경하지 않았다.

변환 방식 참고: [LibreOffice 명령줄 실행](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html), [PDF 내보내기 옵션](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html).

### 공지 목록·iframe 수정 확인 — 2026-10-16

- 오류 재현: 로그인한 상태에서 `/notices` → Nginx 301 `/notices/` → Flask 404. 기존 검사에 목록을 거치는 공개 접속 경로가 빠져 있었다.
- 수정: Nginx의 정확한 `/notices` location과 Flask `strict_slashes=False`로 양쪽 주소를 허용한다. 로그인 후 양쪽 주소가 리디렉션 없이 HTTP 200으로 열리는 것을 운영 브라우저에서 확인했다.
- 공지 안에는 같은 사이트의 독립 HTML 뷰어를 iframe으로 넣는다. 변환은 기존 비권한 서버 작업을 그대로 사용한다. iframe 자체가 PPT를 해석하는 것은 아니다. [iframe 설명](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe), [Microsoft의 OneDrive 기반 임베드 설명](https://support.microsoft.com/en-gb/powerpoint/embed-a-presentation-in-a-web-page-or-blog).
- 제공된 실제 샘플 PPTX는 기존 파일 검증을 통과하고 운영 서버에서 4장 모두 변환됐다. PC 1440px·모바일 390px 화면에서 iframe, 페이지 이동, 키보드, 전체 화면, 별도 창 열기를 확인했다. 브라우저 JavaScript 오류·자동 다운로드·iframe 내부 스크롤 잘림은 없었다. 변환 결과의 한글 화면도 직접 점검했다. 원본 파일은 수정하지 않았다.
- 자동 검사 70개가 Python 3.13·운영 Python 3.10 분리 환경에서 통과했다. 검증용 공지는 삭제하고 관련 원본·이미지 캐시를 정리했다. 운영 DB 스키마는 변경하지 않았다.
- 변경 전 코드·Nginx 설정과 배포 패키지는 `/opt/vicabc-backups/notice-iframe-20261016-nQ0DV9/`에 root 전용으로 보관한다. 롤백 시 이 백업의 기존 파일과 Nginx 공지 설정을 복원하고 서비스를 재시작한다. 새 뷰어 템플릿·CSS는 코드 롤백 후 참조되지 않으므로 남겨도 무방하다. 운영 DB를 과거 시점으로 덮어쓰지 않는다.
