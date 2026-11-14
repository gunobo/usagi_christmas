# usagi.imjemin.co.kr — 8D ASCII Carol + 방명록

- `backend/` FastAPI + PostgreSQL (방명록 API, `/player` 정적 플레이어)
- `app/` Expo(React Native) — 웹 빌드는 nginx로 서빙, 폰 앱은 Expo Go로 실행

## 배포 (라즈베리파이)
```bash
cp .env.example .env   # 값 수정
docker compose up -d --build
```
Cloudflare Tunnel `config.yml` ingress에 추가:
```yaml
- hostname: usagi.imjemin.co.kr
  service: http://localhost:8088
```
```bash
cloudflared tunnel route dns <터널이름> usagi.imjemin.co.kr
```

## 로컬 개발
```bash
docker compose up -d db
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd app && npm i && EXPO_PUBLIC_API_URL=http://<내PC IP>:8000 npx expo start   # 폰: Expo Go로 QR 스캔
```

## 방명록 삭제 (관리자)
```bash
curl -X DELETE https://usagi.imjemin.co.kr/api/guestbook/<id> -H "X-Admin-Token: <ADMIN_TOKEN>"
```

## License
MIT © 2026 임제민 (gunobo) — [LICENSE](LICENSE)
