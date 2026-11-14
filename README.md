# usagi.imjemin.co.kr — 8D ASCII Carol + 방명록

- `backend/` FastAPI + PostgreSQL (방명록 API, `/player` 정적 플레이어)
- `app/` Expo(React Native) — 웹 빌드는 nginx로 서빙, 폰 앱은 Expo Go로 실행

## 배포 (라즈베리파이)
```bash
cp .env.example .env   # 값 수정
docker compose up -d --build
```
Cloudflare Tunnel도 compose 안에서 같이 떠요 (`cloudflared` 서비스).
1. Cloudflare 대시보드 → Zero Trust → Networks → Tunnels → **Create tunnel** (Cloudflared)
2. 발급된 토큰을 `.env`의 `TUNNEL_TOKEN`에 넣기
3. Public Hostname 추가: `usagi.imjemin.co.kr` → Service `HTTP` / `web:80`
4. `docker compose up -d --build`

## 로컬 개발
```bash
docker compose up -d db
cd backend && pip install -r requirements.txt && MEDIA_DIR=./media uvicorn main:app --reload
cd app && npm i && EXPO_PUBLIC_API_URL=http://<내PC IP>:8000 npx expo start   # 폰: Expo Go로 QR 스캔
```

## 방명록 삭제 (관리자)
```bash
curl -X DELETE https://usagi.imjemin.co.kr/api/guestbook/<id> -H "X-Admin-Token: <ADMIN_TOKEN>"
```

## License
MIT © 2026 임제민 (gunobo) — [LICENSE](LICENSE)

## 관리자 페이지
`https://usagi.imjemin.co.kr/admin/` 에서 `.env`의 `ADMIN_TOKEN`으로 접속 → 전체 방명록(IP 포함) 조회·검색·삭제
- **이미지·음원 탭**: 캐릭터 이미지 여러 개 업로드(활성 이미지를 순서대로 번갈아 사용, ◀▶로 순서 변경), 음원 업로드(활성 1개를 8D로 재생, 없으면 기본 징글벨)
- 업로드 파일은 docker 볼륨 `media`에 저장 (이미지 10MB, 음원 40MB 제한)
