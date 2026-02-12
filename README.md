# 📊 모바일 포트폴리오 - 클라우드 배포 가이드

아이폰 홈 화면에서 앱처럼 실행되는 실시간 포트폴리오 관리 시스템입니다.

---

## 🎯 완성되면 이렇게 됩니다

- 아이폰 홈 화면에 앱 아이콘 생성
- 터치하면 전체화면으로 실행 (Safari 주소창 없음)
- 실시간 시세 조회 (네이버 금융)
- 어디서든 접속 가능 (WiFi, LTE, 5G)

---

## 📋 준비물

1. **GitHub 계정** (무료) - https://github.com
2. **Render 계정** (무료) - https://render.com

이미 있으시면 바로 시작!

---

## 🚀 배포 순서 (10분)

### STEP 1: GitHub에 코드 올리기

1. https://github.com 로그인
2. 오른쪽 상단 **+** → **New repository** 클릭
3. 설정:
   - Repository name: `my-portfolio` (아무 이름)
   - **Public** 선택
   - **Add a README file** 체크 해제
4. **Create repository** 클릭

5. 생성된 페이지에서 **uploading an existing file** 링크 클릭
6. 아래 5개 파일을 드래그&드롭:

```
app.py
requirements.txt
templates/index.html    ← templates 폴더째 올리기
static/manifest.json    ← static 폴더째 올리기
static/sw.js
```

⚠️ **중요**: 폴더 구조를 유지해야 합니다!

**폴더째 올리는 방법:**
- 컴퓨터에 아래 구조로 폴더를 만든 후 **전체 폴더를** 드래그하세요:
```
my-portfolio/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    ├── manifest.json
    └── sw.js
```

7. **Commit changes** 클릭

---

### STEP 2: Render에서 서버 만들기

1. https://render.com 접속 → **Get Started for Free**
2. GitHub 계정으로 로그인
3. Dashboard에서 **New +** → **Web Service** 클릭
4. **Build and deploy from a Git repository** 선택
5. 방금 만든 `my-portfolio` 저장소 **Connect** 클릭

6. 설정 입력:

| 항목 | 입력값 |
|------|--------|
| **Name** | `my-portfolio` (아무 이름) |
| **Region** | Singapore (Southeast Asia) ← 한국에서 가장 빠름 |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT` |
| **Instance Type** | **Free** |

7. **Deploy Web Service** 클릭
8. 배포 진행 (2~3분 소요)

완료되면 이런 URL이 생깁니다:
```
https://my-portfolio-xxxx.onrender.com
```

이 URL을 복사해두세요!

---

### STEP 3: 아이폰에 앱 설치

1. 아이폰 **Safari**로 위 URL 접속
2. 하단 **공유 버튼** (□↑) 터치
3. 스크롤해서 **"홈 화면에 추가"** 선택
4. 이름 확인 후 **추가** 터치

끝! 홈 화면에 💼 아이콘이 생깁니다.

---

## 📱 사용법

### 종목 추가
1. 오른쪽 하단 **＋** 버튼
2. 종목명 입력 → 🔍 버튼 → 검색결과에서 선택
3. 수량, 매수가, 섹터 입력
4. **추가** 버튼

### 시세 갱신
- 상단 **🔄 시세갱신** 버튼 터치
- 모든 종목의 현재가가 업데이트됨

### 종목 수정/삭제
- 종목 카드를 터치하면 수정/삭제 버튼 표시

### 뷰 전환
- **📋 목록**: 상세 카드 뷰
- **🗺️ 맵**: 트리맵 시각화

---

## ⚠️ 알아두실 것

### 무료 서버 특성
- Render 무료 플랜은 **15분 미사용 시 서버가 절전 모드**로 전환됩니다
- 다시 접속하면 **30초~1분 정도** 기다리면 깨어납니다
- 한번 깨어나면 이후에는 즉시 응답합니다

### 데이터 저장
- 포트폴리오 데이터는 **아이폰 브라우저(Safari)**에 저장됩니다
- Safari 데이터를 초기화하면 포트폴리오도 삭제됩니다
- 다른 기기에서 접속하면 별도의 포트폴리오가 생성됩니다

### 시세 조회
- 장 마감 후에도 조회 가능 (종가 표시)
- 네이버 금융 데이터 기준
- 대량 조회 시 네이버 차단 방지를 위해 약간의 딜레이가 있음

---

## 🔧 문제 해결

### 서버가 안 뜹니다
1. Render Dashboard에서 서버 상태 확인
2. Logs 탭에서 오류 확인
3. Build Command, Start Command가 정확한지 확인

### "홈 화면에 추가"가 안 보입니다
- **반드시 Safari**에서 열어야 합니다 (Chrome에서는 안 됨)
- 공유 버튼 → 스크롤 내려보면 있습니다

### 시세가 안 나옵니다
- 서버가 절전 모드일 수 있음 → 30초 기다린 후 다시 시도
- 인터넷 연결 확인

---

## 📁 파일 구조

```
my-portfolio/
├── app.py              # 서버 (Flask + 네이버 스크래핑)
├── requirements.txt    # Python 패키지
├── templates/
│   └── index.html      # 모바일 PWA 프론트엔드
└── static/
    ├── manifest.json   # PWA 설정
    └── sw.js           # 오프라인 캐시
```

---

## 💡 업그레이드 팁

### 서버 절전 없애기
- Render 유료 플랜 ($7/월) 사용 시 항시 가동
- 또는 UptimeRobot (무료)으로 5분마다 핑을 보내서 절전 방지

### 자동 시세 갱신
- `index.html`에서 자동 갱신 주기 설정 가능
- 서버 부하를 고려해 5분 이상 권장

---

**이제 시작하세요!** 🚀

GitHub → Render → Safari → 홈 화면 추가 → 완성!
