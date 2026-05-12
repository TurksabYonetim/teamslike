# TeamsLike API — Kullanım Kılavuzu

TeamsLike, SaaS uygulamalarına gömülebilen bir **mesajlaşma + görüntülü görüşme + randevu** backend'idir. Müşteri-tarafı ve personel-tarafı sohbet, Jitsi tabanlı meeting, tarih bazlı randevu ve takım içi DM tek bir API üzerinden yönetilir.

- **Base URL** (lokal geliştirme): `http://127.0.0.1:8800`
- **OpenAPI**: `GET /openapi.json` · **Swagger UI**: `GET /docs` · **ReDoc**: `GET /redoc`
- **Sürüm**: `0.1.0`
- **Auth**: `Authorization: Bearer <token>` (JWT, HS256)

---

## İçindekiler

1. [Hızlı başlangıç](#hızlı-başlangıç)
2. [Mimari kavramlar](#mimari-kavramlar)
3. [İki kimlik tipi: staff JWT vs external identity JWT](#iki-kimlik-tipi)
4. [Endpoint referansı](#endpoint-referansı)
   - [Auth](#auth)
   - [Tenants](#tenants)
   - [Users](#users)
   - [Portal — external user](#portal--external-user)
   - [Inbox — staff](#inbox--staff)
   - [Meetings — Jitsi](#meetings--jitsi)
   - [Direct messages — team chat](#direct-messages--team-chat)
   - [Appointments](#appointments)
   - [Legacy Chatwoot endpoint'leri](#legacy-chatwoot)
5. [Entegrasyon rehberi (üçüncü-parti SaaS)](#entegrasyon-rehberi)
6. [Hata formatı ve HTTP kodları](#hata-formatı)
7. [Güvenlik notları](#güvenlik-notları)

---

## Hızlı başlangıç

```bash
# 1) Yeni bir tenant aç + ilk admin kullanıcıyı yarat
curl -X POST http://127.0.0.1:8800/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_slug": "acme",
    "tenant_name": "Acme Inc.",
    "admin_email": "admin@acme.com",
    "admin_full_name": "Acme Admin",
    "admin_password": "supersecret"
  }'
# Dönen tokens.access_token = staff JWT

# 2) Tenant'a özel signing secret'ı al (admin token gerekir)
curl -H "Authorization: Bearer $STAFF_TOKEN" \
     http://127.0.0.1:8800/v1/tenants/me/signing-secret

# 3) Kendi backend'inde bu secret ile end-user için kısa-ömürlü JWT imzala
#    (claims: iss=tenant_slug, sub=<end_user_id>, email, name, exp)

# 4) End-user tarayıcısı bu JWT ile /v1/portal/me/* endpoint'lerini kullanır
```

Üretimde tipik akış: tenant `signup` ile bir kere kayıt olur, **signing_secret** kendi backend'inizde saklanır, bundan sonra her end-user için server-side JWT mintleyip frontend'inize verirsiniz. Bizim DB'de end-user kaydı tutulmaz.

---

## Mimari kavramlar

| Kavram | Açıklama |
|---|---|
| **Tenant** | Bir müşteri organizasyonu (sizin SaaS uygulamanız). Slug ile tanımlı, kendi `signing_secret`'ı vardır. |
| **User (staff)** | Tenant'ın çalışanı. `owner` / `admin` / `member` rollerinden biri. Email/parola ile login olur. |
| **External identity** | Tenant'ın son kullanıcısı (alıcı / müşteri / vatandaş). **TeamsLike DB'sinde kaydı yoktur.** Tenant-imzalı JWT ile kanıtlanır. |
| **Per-user inbox** | Her staff user'ın kendi Chatwoot inbox'ı vardır (`teamslike-u-<user_uuid>`). External user'lar belirli bir staff'a yazar; aynı tenant'taki başka staff o thread'i görmez. |
| **Signing secret** | Tenant'a özel 32-byte URL-safe random string. End-user JWT'lerini bu secret ile imzalarsınız. Sadece bir kez gösterilir + rotate edilebilir. |

Geliştirme: API + Chatwoot + Jitsi + Postgres + Redis hepsi `docker-compose` ile lokal ayağa kalkar. Detay için `CREDENTIALS.md`.

---

## İki kimlik tipi

### A. Staff JWT (`kind: "staff"`)

Tenant çalışanları kullanır. `/v1/auth/login` ile alınır. 60 dakika geçerli (env: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).

**Claims** (HS256 ile tenant-bağımsız `JWT_SECRET_KEY` ile imzalı):

```json
{
  "sub": "<user_uuid>",
  "tid": "<tenant_uuid>",
  "role": "owner|admin|member",
  "email": "...",
  "kind": "staff",
  "type": "access",
  "exp": 1234567890
}
```

Kullanır: `/v1/users/...`, `/v1/inbox/...`, `/v1/meetings/...`, `/v1/dm/...`, `/v1/appointments/...`, `/v1/tenants/me/...`.

### B. External identity JWT (`iss: tenant_slug`)

End-user'ı temsil eder. **Tenant'ın kendi backend'inde** `signing_secret` ile imzalanır. TeamsLike sadece doğrular; DB'ye yazmaz.

**Gerekli claims**:

```json
{
  "iss": "<tenant_slug>",   // hangi tenant'ın user'ı
  "sub": "<your_user_id>",  // sizin sistemdeki user ID (string)
  "email": "user@example.com",
  "name": "Display Name",
  "iat": 1234567890,
  "exp": 1234571490         // önerilen TTL: 1 saat
}
```

Algoritma: **HS256**. Kullanır: `/v1/portal/me/...`.

---

## Endpoint referansı

> Tüm `Bearer` header'lı çağrılar `Authorization: Bearer <token>` ister. JSON body'ler `Content-Type: application/json` ile gönderilir.

### Auth

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `POST` | `/v1/auth/signup` | — | Yeni tenant + ilk admin (`owner`) yarat. |
| `POST` | `/v1/auth/login` | — | Staff JWT al. Body: `{tenant_slug, email, password}`. |
| `POST` | `/v1/auth/register-user` | — | Mevcut tenant'a `member` rolünde yeni kullanıcı kayıt. Body: `{tenant_id (UUID), email, full_name, password}`. |
| `GET` | `/v1/auth/me` | Staff | Token sahibinin bilgilerini döner. |

**Örnek — login**:

```bash
curl -X POST http://127.0.0.1:8800/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"acme","email":"admin@acme.com","password":"supersecret"}'
# → {"access_token":"eyJ…", "refresh_token":"eyJ…", "token_type":"bearer"}
```

### Tenants

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `GET` | `/v1/tenants/me` | Staff | Mevcut tenant. |
| `GET` | `/v1/tenants/me/signing-secret` | Admin | Tenant'ın signing_secret'ı (end-user JWT imzalamak için). |
| `POST` | `/v1/tenants/me/rotate-signing-secret` | Admin | Yeni secret üret. Eski JWT'ler invalidate olur. |

### Users

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `GET` | `/v1/users/` | Staff | Tenant'taki kullanıcıların listesi. |
| `POST` | `/v1/users/` | Admin | Yeni member kullanıcı oluştur. Body: `{email, full_name, password, role}` (role default: `member`). |
| `GET` | `/v1/users/{user_id}` | Staff | Tek kullanıcı. |

### Portal — external user

End-user'ın kendi kimliğiyle kullandığı endpoint'ler. **Authorization: tenant-signed JWT**.

| Method | Path | Açıklama |
|---|---|---|
| `GET` | `/v1/portal/me/whoami` | Doğrulanan kimliğin claims'i (debug için faydalı). |
| `GET` | `/v1/portal/me/tenants` | Bizim sistemdeki tenant'ların listesi (`tenant_id`, `slug`, `name`). |
| `GET` | `/v1/portal/me/sellers?tenant_id=<uuid>` | Bir tenant'ın staff kullanıcılarını ("seller"/"agent") listele. |
| `POST` | `/v1/portal/me/threads` | Bir staff ile thread başlat. Body: `{seller_user_id, initial_message?}`. Aynı kişiyle ikinci kez çağrı idempotent (varolan thread döner). |
| `GET` | `/v1/portal/me/threads` | End-user'ın tüm thread'leri. |
| `GET` | `/v1/portal/me/threads/{conversation_id}/messages` | Thread içindeki mesajlar (Chatwoot şeması: `message_type: 0=user, 1=staff, 2=activity`). |
| `POST` | `/v1/portal/me/threads/{conversation_id}/messages` | Mesaj yolla. Body: `{content}`. |

**Örnek — end-user JWT imzalama (Python)**:

```python
from jose import jwt
import time

token = jwt.encode(
    {"iss": "acme", "sub": "cust_123", "email": "ali@x.com",
     "name": "Ali", "iat": int(time.time()), "exp": int(time.time()) + 3600},
    signing_secret, algorithm="HS256",
)
```

### Inbox — staff

Staff'in kendi inbox'ına yazılan external user thread'lerini gördüğü endpoint'ler. **Authorization: staff JWT**.

| Method | Path | Açıklama |
|---|---|---|
| `GET` | `/v1/inbox/threads` | Şu anki staff'a yazılan tüm thread'ler (per-user inbox). |
| `GET` | `/v1/inbox/threads/{conversation_id}/messages` | Mesajlar. |
| `POST` | `/v1/inbox/threads/{conversation_id}/messages` | Staff cevabı. Conversation staff'in inbox'ında değilse `404`. |

### Meetings — Jitsi

JWT-modunda Jitsi odaları + moderator/guest token üretimi.

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `POST` | `/v1/meetings/` | Staff | Oda + moderator JWT oluştur. Body: `{title, scheduled_at (ISO datetime), duration_minutes}`. Response'da `join_url` (host moderator olarak) ve `room_name`. |
| `GET` | `/v1/meetings/` | Staff | Tenant'ın meeting'lerini listele. |
| `POST` | `/v1/meetings/{meeting_id}/guest-token` | Staff | Misafir için JWT/URL. Body: `{guest_name}`. |

**Örnek — meeting oluştur**:

```bash
curl -X POST http://127.0.0.1:8800/v1/meetings/ \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Sync","scheduled_at":"2026-05-12T15:00:00","duration_minutes":30}'
```

Response `join_url` formatı: `https://<JITSI_PUBLIC_URL>/<room_name>?jwt=<moderator_jwt>`.

### Direct messages — team chat

Aynı tenant'taki iki staff kullanıcı arasında DM. **Authorization: staff JWT**.

| Method | Path | Açıklama |
|---|---|---|
| `POST` | `/v1/dm/messages` | DM gönder. Body: `{recipient_user_id, content}`. |
| `GET` | `/v1/dm/threads` | Konuştuğum thread'ler (counterparty + son mesaj + unread). |
| `GET` | `/v1/dm/threads/{other_user_id}/messages?since=<iso>` | Bir kullanıcıyla thread içindeki mesajlar (polling için `since` paramı). |
| `POST` | `/v1/dm/threads/{other_user_id}/read` | Bu kişiden gelen mesajları okundu işaretle. |

### Appointments

Tarih bazlı randevu (opsiyonel meeting bağlı). **Authorization: staff JWT**.

| Method | Path | Açıklama |
|---|---|---|
| `POST` | `/v1/appointments/` | Randevu oluştur. Body: `{title, description, start_at, end_at, attendee_emails[], create_meeting (bool)}`. `create_meeting=true` ise otomatik Jitsi meeting bağlanır. Organizatörün çakışan randevusu varsa `409`. |
| `GET` | `/v1/appointments/?start=<iso>&end=<iso>` | Tenant randevularını listele (tarih aralığı opsiyonel). |
| `DELETE` | `/v1/appointments/{appointment_id}` | Sil. |

### Legacy Chatwoot

Eski Chatwoot direct entegrasyonu — ham conversation/message API'si. Yeni entegrasyonlar için `/v1/portal/me/...` ve `/v1/inbox/...` önerilir.

| Method | Path | Açıklama |
|---|---|---|
| `GET` | `/v1/conversations/` | Tenant'ın tüm Chatwoot conversation'ları. |
| `POST` | `/v1/conversations/` | Manuel conversation oluştur. Body: `{contact_name, contact_email, inbox_id, initial_message}`. |
| `POST` | `/v1/conversations/{id}/messages` | Mesaj yolla. |
| `GET` | `/v1/conversations/inboxes` | Chatwoot inbox listesi. |
| `POST` | `/v1/conversations/inboxes/ensure-default` | Tenant için default inbox auto-provision. |

---

## Entegrasyon rehberi

Bir SaaS uygulamasını TeamsLike API ile entegre ederken tipik akış:

### 1) Bir kez: tenant kaydı

```python
import httpx

r = httpx.post("http://api.teamslike.local/v1/auth/signup", json={
    "tenant_slug": "myapp",
    "tenant_name": "My App",
    "admin_email": "ops@myapp.com",
    "admin_full_name": "Ops",
    "admin_password": "…",
})
admin_token = r.json()["tokens"]["access_token"]

sec = httpx.get(
    "http://api.teamslike.local/v1/tenants/me/signing-secret",
    headers={"Authorization": f"Bearer {admin_token}"},
).json()["signing_secret"]

# admin_token ve sec'i **server-side** sakla; browser'a vermeyin
```

### 2) Her staff kullanıcı

`/v1/users/` üzerinden tenant admin'in oluşturduğu staff'lar. Login akışı: `/v1/auth/login` → frontend access_token'ı saklar (cookie/localStorage) → her staff endpoint çağrısında Bearer header.

### 3) Her end-user

Sizin uygulamanızda zaten oturum açmış bir kullanıcı (örn. bir alıcı). **Sizin backend'inizde** o kullanıcı için tenant secret ile JWT mintleyin ve frontend'e teslim edin:

```python
from jose import jwt
import time

def chat_token_for_user(user_id, email, name):
    return jwt.encode(
        {"iss": "myapp", "sub": str(user_id),
         "email": email, "name": name,
         "iat": int(time.time()), "exp": int(time.time()) + 3600},
        SIGNING_SECRET, algorithm="HS256",
    )
```

Frontend bu token'ı `Authorization: Bearer <token>` ile TeamsLike `/v1/portal/me/*` endpoint'lerine yollar.

### 4) Mesajlaşma akışı

```text
end-user                                          staff
    |  POST /portal/me/threads                       |
    |     {seller_user_id, initial_message}          |
    |----------> TeamsLike API ---------------------→|
    |                                                | GET /inbox/threads  ← yeni thread görünür
    |                                                |
    |                                                | POST /inbox/threads/{id}/messages
    |  POST /portal/me/threads/{id}/messages         |
    |  GET ...                                       |
```

### 5) Video çağrısı

Staff veya backend `/v1/meetings/` ile oda oluşturur. Diğer taraflar için `/v1/meetings/{id}/guest-token` ile JWT üretilir. Linkler `https://<JITSI_PUBLIC_URL>/<room>?jwt=…`. Tarayıcılar `JITSI_PUBLIC_URL` Self-signed cert kullanıyorsa bir kez kabul gerekir.

---

## Hata formatı

Tüm hatalar standart şekilde döner:

```json
{ "detail": "Insan-okunur hata mesajı" }
```

| Status | Anlamı | Tipik nedenler |
|---|---|---|
| `400` | Geçersiz girdi | Validasyon, business rule (ör. appointment start>end) |
| `401` | Auth eksik / geçersiz | Token yok, süresi dolmuş, kötü signature, kötü `iss` |
| `403` | Yetersiz rol | Admin gerektiren endpoint'e member ile çağrı |
| `404` | Bulunamadı | ID yanlış, scope dışı (başka tenant'ın kaynağı) |
| `409` | Çakışma | Email duplicate, randevu çakışması, slug taken |
| `502` | Provider hatası | Chatwoot/Jitsi cevap vermedi |

### Pydantic validasyon hatası

Pydantic'in detay formatı (FastAPI default):

```json
{
  "detail": [
    {"type":"missing","loc":["body","email"],"msg":"Field required",...}
  ]
}
```

---

## Güvenlik notları

- **`signing_secret` server-side kalır.** Tarayıcıya bırakırsanız uygulama JWT istimal edilebilir. Sadece kendi backend'inizde tutun.
- **Kısa TTL**: end-user JWT'leri 1 saat civarında tutun. Yenileme her sayfa yüklenmesinde yapılabilir.
- **`rotate-signing-secret`** — gerekli durumda (sızıntı şüphesi) çağırın. Tüm aktif end-user token'ları invalidate olur. Frontend'ler yeni token alıp devam eder.
- **CORS**: Geliştirmede `allow_origins=["*"]`. Üretimde tenant domain'i kısıtlayın.
- **TLS**: Üretimde mutlaka HTTPS (terminator nginx vb.). Self-signed cert'leri yalnızca lokal'de kullanın.
- **Rate limit**: Şu an yok. Tenant başına rate limit eklemek için reverse proxy veya WAF kullanın.
- **Multi-tenant izolasyon**: `tid` claim'i ile staff endpoint'leri, `iss` ile portal endpoint'leri tenant scope dışına çıkmaz.

---

## Yardımcı kaynaklar

- **Swagger UI** (canlı oyna): `http://127.0.0.1:8800/docs`
- **API Explorer** (testapp içi): `http://192.168.1.163:8090/explorer/` — endpoint listesi + form üretici + auth picker + cURL preview
- **Demo uygulama** (testbaba): `http://192.168.1.163:8091/` — end-user / seller / admin akışlarının çalışan örneği
- **Credentials & runtime detayları**: repo kökündeki `CREDENTIALS.md`
