# TeamsLike API — Recipes

Yaygın senaryolar için uçtan uca tarif kitabı. Her tarif: **ne yapacaksın → endpoint sırası → çalışan kod**. Genel kullanım kılavuzu için [`API.md`](./API.md).

| # | Senaryo | Anahtar endpoint'ler |
|---|---|---|
| 1 | [Marketplace MVP (Alibaba/Hepsiburada tarzı)](#recipe-1-marketplace-mvp) | `/v1/users` · `/v1/portal/me/*` · `/v1/inbox/*` |
| 2 | [Müşteri destek hattı](#recipe-2-müşteri-destek-hattı) | `/v1/portal/me/*` · `/v1/inbox/*` |
| 3 | [Online danışmanlık (randevu + video)](#recipe-3-online-danışmanlık-randevu--video) | `/v1/appointments` · `/v1/meetings` |
| 4 | [Slack-vari iç ekip sohbeti](#recipe-4-slack-vari-iç-ekip-sohbeti) | `/v1/dm/*` |
| 5 | [Tenant onboarding & secret rotation](#recipe-5-tenant-onboarding-ve-secret-rotation) | `/v1/auth/signup` · `/v1/tenants/me/*` |
| 6 | [Web sitesine gömülebilir chat widget](#recipe-6-web-sitesine-gömülebilir-chat-widget) | `/v1/portal/me/*` |
| 7 | [Polling stratejisi (websocket'siz)](#recipe-7-polling-stratejisi) | `since=` query, `lastSeenAt` |
| 8 | [DM içinden video çağrısı başlatma](#recipe-8-dm-içinden-video-çağrısı-başlatma) | `/v1/meetings` · `/v1/dm/*` |
| 9 | [Tenant-genelinde tüm sohbetleri moderasyon](#recipe-9-tenant-genelinde-tüm-sohbetleri-moderasyon) | `/v1/conversations` |
| 10 | [Cross-domain JWT cüzdanı (single sign-on benzeri)](#recipe-10-cross-domain-jwt-cüzdanı) | `iss` claim + frontend cookies |

> Tüm örnekler bash + Python kullanır. JS karşılıkları doğrudan `fetch` ile çevrilebilir.

---

## Recipe 1: Marketplace MVP

**Senaryo**: testbaba.com gibi. Bir tenant (platform), N satıcı (her biri staff user), M müşteri (her biri external identity).

```
Platform (tenant=acme)
├── Staff user A (seller "Shenzhen Lighting")
├── Staff user B (seller "Berlin Bike Parts")
└── ...
Customers (external identities, DB'de kayıt yok)
└── buyer_001, buyer_002, ...
```

### Adımlar

```bash
# (1) Platform admin tenant'ı kurar
curl -X POST http://api.local/v1/auth/signup -H 'Content-Type: application/json' -d '{
  "tenant_slug":"acme","tenant_name":"Acme Marketplace",
  "admin_email":"ops@acme.com","admin_full_name":"Ops","admin_password":"opspass1234"
}'
# → admin staff JWT

# (2) Admin signing_secret'ı server-side saklar
curl -H "Authorization: Bearer $ADMIN" \
     http://api.local/v1/tenants/me/signing-secret
# → "kKQ9...43-byte"

# (3) Admin her satıcıyı staff user olarak ekler
curl -X POST http://api.local/v1/users/ \
  -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"shenzhen@acme.com","full_name":"Shenzhen Lighting",
       "password":"sellerpass","role":"member"}'

# (4) Müşteri sitenizde login olur, sizin backend chat-token verir
#     (aşağıdaki Python snippet)

# (5) Müşteri tarayıcısı satıcılarla mesajlaşır
curl -X POST http://api.local/v1/portal/me/threads \
  -H "Authorization: Bearer $CHAT_TOKEN" -H 'Content-Type: application/json' \
  -d '{"seller_user_id":"<staff_uuid>","initial_message":"Merhaba!"}'

# (6) Satıcı kendi inbox'ından mesajları görür ve cevaplar
curl -H "Authorization: Bearer $SELLER_STAFF_TOKEN" \
     http://api.local/v1/inbox/threads
```

### Sizin backend (Python) — müşteri chat-token üretimi

```python
from jose import jwt
import time

SIGNING_SECRET = os.environ["TEAMSLIKE_SIGNING_SECRET"]
TENANT_SLUG = "acme"

def chat_token_for(buyer):
    now = int(time.time())
    return jwt.encode({
        "iss": TENANT_SLUG,
        "sub": str(buyer.id),
        "email": buyer.email,
        "name": buyer.full_name,
        "iat": now,
        "exp": now + 3600,
    }, SIGNING_SECRET, algorithm="HS256")

# Flask route örneği:
@app.get("/me/chat-token")
def chat_token():
    return {"token": chat_token_for(current_user)}
```

### Frontend — müşteri tarafı (örnek fetch)

```js
const tok = (await fetch("/me/chat-token").then(r => r.json())).token;

// Listele
const sellers = await fetch("/api/v1/portal/me/sellers", {
  headers: { Authorization: `Bearer ${tok}` },
}).then(r => r.json());

// Thread aç + mesaj yolla
const thread = await fetch("/api/v1/portal/me/threads", {
  method: "POST",
  headers: { "Content-Type":"application/json", Authorization: `Bearer ${tok}` },
  body: JSON.stringify({ seller_user_id: sellers[0].user_id, initial_message:"Selam" }),
}).then(r => r.json());
```

---

## Recipe 2: Müşteri destek hattı

**Senaryo**: SaaS uygulamanızda "Help" widget'ı. Kullanıcı destek ekibine yazar.

Marketplace'le aynı API'yi kullanır; tek fark: destek ekibi `support_team` etiketli kullanıcılardır. Mesaj routing aynı (per-user inbox).

### Tek bir "destek" havuzu için: bir support user'ı

Her destek talebini aynı staff user'a (örn. `support@yourapp.com`) yönlendirebilirsin:

```js
// frontend: kullanıcı "Help"e tıkladığında
const supportUser = (await fetch("/api/v1/portal/me/sellers", {
  headers: { Authorization: `Bearer ${chatToken}` },
}).then(r => r.json())).find(u => u.email === "support@yourapp.com");

const thread = await fetch("/api/v1/portal/me/threads", {
  method: "POST",
  headers: { "Content-Type":"application/json", Authorization: `Bearer ${chatToken}` },
  body: JSON.stringify({ seller_user_id: supportUser.user_id }),
}).then(r => r.json());
```

### Birden fazla agent — round-robin

Backend, custom logic ile uygun agent'ı seçer:

```python
def pick_agent_for(buyer):
    agents = httpx.get(API + "/v1/portal/me/sellers", headers={...}).json()
    agents = [a for a in agents if a["email"].startswith("support+")]
    return random.choice(agents)  # ya da least-busy
```

Sonra `seller_user_id` olarak bunu gönder.

---

## Recipe 3: Online danışmanlık (randevu + video)

**Senaryo**: psikolog/avukat/doktor — randevu rezerve edilir, zamanı gelince video call açılır.

### Akış

```
1. Buyer rezervasyon talep eder
2. Staff kullanıcı (uzman) randevuyu onaylar — appointment yaratır, create_meeting: true
3. API bağlı bir Jitsi meeting üretir; appointment'a iliştirir
4. Randevu zamanı gelince taraflar join_url üzerinden katılır
```

### Backend (uzman tarafı, staff JWT)

```bash
curl -X POST http://api.local/v1/appointments/ \
  -H "Authorization: Bearer $STAFF" -H 'Content-Type: application/json' \
  -d '{
    "title":"Dr. X — checkup",
    "description":"30 dk genel kontrol",
    "start_at":"2026-05-15T10:00:00",
    "end_at":  "2026-05-15T10:30:00",
    "attendee_emails":["alice@buyer.com"],
    "create_meeting": true
  }'
# → appointment + meeting_id bağlı
```

### Buyer için meeting linki

Appointment listesinde `meeting_id` görünür. Buyer için guest token alın ve email/SMS ile gönderin:

```bash
curl -X POST http://api.local/v1/meetings/$MID/guest-token \
  -H "Authorization: Bearer $STAFF" -H 'Content-Type: application/json' \
  -d '{"guest_name":"Alice"}'
# → {"room_name":"…","guest_token":"…","join_url":"https://jitsi/…?jwt=…"}
```

> Üretimde **email gönderme**: tenant'ın kendi backend'inden. Bizim API email göndermez.

### Çakışma kontrolü

`/v1/appointments/` aynı `organizer_user_id` için tarih çakışması varsa **409** döner. Frontend bunu yakalar:

```js
const res = await fetch("/api/v1/appointments/", {...});
if (res.status === 409) {
  alert("Bu saatte başka randevunuz var");
}
```

---

## Recipe 4: Slack-vari iç ekip sohbeti

**Senaryo**: tenant'ın **çalışanları** birbirine DM atsın. Müşterilerden bağımsız.

`/v1/dm/*` endpoint'leri **staff JWT** ile çalışır; aynı tenant'taki iki user arası mesajlaşmayı sağlar.

### Mesaj at + thread takip

```bash
# Bana mesaj kimden geldi?
curl -H "Authorization: Bearer $ME" http://api.local/v1/dm/threads
# → [{counterparty:{user_id,...}, last_message, unread_count}, ...]

# Bir kişiyle thread:
curl -H "Authorization: Bearer $ME" \
     "http://api.local/v1/dm/threads/<other_uid>/messages?since=2026-05-12T08:00:00"

# Yolla:
curl -X POST http://api.local/v1/dm/messages \
  -H "Authorization: Bearer $ME" -H 'Content-Type: application/json' \
  -d '{"recipient_user_id":"<other_uid>","content":"yarın 10:00 ok?"}'

# Okundu işaretle (sidebar'da rozeti kaldırır):
curl -X POST -H "Authorization: Bearer $ME" \
     http://api.local/v1/dm/threads/<other_uid>/read
```

### Polling pattern

Frontend her N saniyede `?since=<lastSeenAt>` ile yeni mesajları çeker:

```js
const POLL = 3000;
let lastSeen = null;

setInterval(async () => {
  const url = `/api/v1/dm/threads/${other_uid}/messages` +
              (lastSeen ? `?since=${encodeURIComponent(lastSeen)}` : "");
  const msgs = await fetch(url, { headers }).then(r => r.json());
  for (const m of msgs) {
    appendBubble(m);
    if (m.created_at > (lastSeen || "")) lastSeen = m.created_at;
  }
}, POLL);
```

---

## Recipe 5: Tenant onboarding ve secret rotation

### Onboarding — sıfırdan operatörlü kurulum

```bash
# 1) signup → admin JWT + user/tenant ID'leri
SIGNUP=$(curl -s -X POST http://api.local/v1/auth/signup -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"newtenant","tenant_name":"New Tenant",
       "admin_email":"admin@new.com","admin_full_name":"Admin","admin_password":"…"}')
ADMIN=$(echo "$SIGNUP" | jq -r .tokens.access_token)
TENANT_ID=$(echo "$SIGNUP" | jq -r .tenant.id)

# 2) signing_secret çek + kendi backend'inde sakla
SECRET=$(curl -s -H "Authorization: Bearer $ADMIN" \
  http://api.local/v1/tenants/me/signing-secret | jq -r .signing_secret)
echo "$SECRET" > /etc/yourapp/teamslike-secret  # 0600 izinle

# 3) (opsiyonel) ekstra admin/member ekle
curl -X POST http://api.local/v1/users/ \
  -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"agent@new.com","full_name":"Agent","password":"…","role":"member"}'
```

### Secret rotation — zero-downtime

Sızıntı şüphesi veya zamanlanmış rotasyon:

```bash
# Eski + yeni secret'ı bir süre paralel tutmak istiyorsan API tek slot tutuyor.
# 1) Yeni secret üret
NEW=$(curl -s -X POST -H "Authorization: Bearer $ADMIN" \
  http://api.local/v1/tenants/me/rotate-signing-secret | jq -r .signing_secret)

# 2) Hemen backend'inin SIGNING_SECRET'ini güncelle (env reload veya process restart)

# 3) Hâlihazırdaki end-user JWT'leri invalidate olur — frontend'ler
#    bir sonraki chat-token isteğinde yenisini alır (siz POST /me/chat-token endpoint'inizden
#    yeni secret ile mintlersiniz).
```

> **TTL düşük tut** (3600 sn). Rotasyon sonrası en kötü ihtimalle 1 saat boyunca eski token'lar 401 alır.

---

## Recipe 6: Web sitesine gömülebilir chat widget

**Senaryo**: e-ticaret sitenizin sağ alt köşesinde "Chat with seller" widget'ı.

### Sayfaya iframe / div + JS gömü

```html
<!-- example: e-ticaret ürün sayfası -->
<div id="tl-widget" data-seller="acme-shenzhen-uuid"></div>
<script>
(async () => {
  // 1) Sitenizin backend'inden kısa-ömürlü chat token al
  const tok = (await fetch("/api/me/chat-token").then(r => r.json())).token;

  // 2) Thread'i aç (idempotent — varsa yeniden döner)
  const thread = await fetch("/api/v1/portal/me/threads", {
    method: "POST",
    headers: { "Content-Type":"application/json", Authorization: `Bearer ${tok}` },
    body: JSON.stringify({ seller_user_id: document.getElementById("tl-widget").dataset.seller })
  }).then(r => r.json());

  // 3) Mesajları render et + polling
  const stream = document.createElement("div");
  document.getElementById("tl-widget").appendChild(stream);

  async function tick() {
    const msgs = await fetch(`/api/v1/portal/me/threads/${thread.id}/messages`,
      { headers: { Authorization: `Bearer ${tok}` } }).then(r => r.json());
    stream.innerHTML = msgs.filter(m => m.message_type !== 2).map(m =>
      `<div class="${m.message_type === 0 ? 'me' : 'them'}">${m.content}</div>`).join("");
  }
  tick();
  setInterval(tick, 3000);
})();
</script>
```

Compose'unuzda nginx zaten `/api/v1/...` proxy yapıyorsa bu CORS-siz çalışır. Cross-origin senaryoda TeamsLike CORS açık.

---

## Recipe 7: Polling stratejisi

API websocket sunmuyor; **polling** ile real-time hissi sağlanır.

### Konversation paneli (3 sn polling)

```js
const POLL_MS = 3000;
let lastSeen = null;
let timer = null;

function startPolling(convId) {
  if (timer) clearInterval(timer);
  timer = setInterval(async () => {
    const qs = lastSeen ? `?since=${encodeURIComponent(lastSeen)}` : "";
    const msgs = await fetch(`/api/v1/portal/me/threads/${convId}/messages${qs}`,
      { headers }).then(r => r.json());
    for (const m of msgs) {
      append(m);
      if (m.created_at > (lastSeen || "")) lastSeen = m.created_at;
    }
  }, POLL_MS);
}
```

### Sidebar (10 sn)

Aktif olmayan thread'lerde okunmamış mesaj rozetini güncellemek için daha seyrek poll (10-15 sn). `/v1/dm/threads` ve `/v1/inbox/threads`’in `unread_count` alanı kullanılır.

### Tab görünür değilken durdur

```js
document.addEventListener("visibilitychange", () => {
  if (document.hidden && timer) clearInterval(timer);
  if (!document.hidden && activeConv) startPolling(activeConv);
});
```

---

## Recipe 8: DM içinden video çağrısı başlatma

**Pattern**: bir DM thread'inde kamera butonuna bas → meeting oluştur → invite mesajı olarak posta → tıklayan join'le.

### Frontend (staff'tan staff'a)

```js
async function startCall(otherUid) {
  const me = await fetch("/api/v1/auth/me", { headers }).then(r => r.json());
  const title = `Call: ${me.email}`;

  // 1) Meeting oluştur
  const meeting = await fetch("/api/v1/meetings/", {
    method: "POST",
    headers: { "Content-Type":"application/json", ...headers },
    body: JSON.stringify({
      title, scheduled_at: new Date().toISOString(), duration_minutes: 60,
    }),
  }).then(r => r.json());

  // 2) DM içine işaret koy
  await fetch("/api/v1/dm/messages", {
    method: "POST",
    headers: { "Content-Type":"application/json", ...headers },
    body: JSON.stringify({
      recipient_user_id: otherUid,
      content: `🎥 [video-call] ${meeting.id} | ${title}`,
    }),
  });

  // 3) Caller direkt katılır (moderator URL)
  window.open(meeting.join_url, "_blank", "noopener");
}
```

### Karşı taraf mesajı parse eder

```js
const CALL_RE = /^🎥 \[video-call\] ([0-9a-fA-F-]{36})\s*\|\s*(.*)$/;

for (const m of messages) {
  const call = (m.content || "").match(CALL_RE);
  if (call) {
    const [, meetingId, title] = call;
    renderJoinButton(meetingId, title);
  }
}

async function joinAs(name, meetingId) {
  const g = await fetch(`/api/v1/meetings/${meetingId}/guest-token`, {
    method: "POST",
    headers: { "Content-Type":"application/json", ...headers },
    body: JSON.stringify({ guest_name: name }),
  }).then(r => r.json());
  window.open(g.join_url, "_blank", "noopener");
}
```

### Token mesaja gömme

Mesaja JWT gömmüyoruz — TTL biter. Her tıklamada `guest-token` ile **taze JWT** alıyoruz; aynı `meeting_id` farklı zamanlarda hep aynı odaya bağlar.

---

## Recipe 9: Tenant-genelinde tüm sohbetleri moderasyon

**Senaryo**: platform operatörü tüm sohbetleri görüntüleyebilsin (kullanım denetimi, ihlal taraması).

```bash
curl -H "Authorization: Bearer $ADMIN" http://api.local/v1/conversations/
# → tenant'a ait tüm Chatwoot conversation kayıtları
```

> **Not**: bu legacy/Chatwoot direkt listesi. Per-user inbox modelinde de aynı veri görünür çünkü tüm threadler tenant'ın inbox'larında durur. İçerikleri okumak için Chatwoot tarafından conversation_id ile mesajlar çekilebilir.

### Otomatik moderasyon hook'u

Kendi cron'u yaz:

```python
import httpx, time
while True:
    convs = httpx.get(API + "/v1/conversations/", headers={"Authorization": f"Bearer {ADMIN}"}).json()
    for c in convs:
        # son N mesajı çek (Chatwoot endpoint'i veya kendi cache'inden)
        # sentiment/küfür/spam taraması
        pass
    time.sleep(60)
```

Üretim için: webhook desteği yok, polling ile çalıştır.

---

## Recipe 10: Cross-domain JWT cüzdanı

**Senaryo**: aynı kullanıcının birden fazla tenant'ta external identity'si var. Kullanıcı her tenant için ayrı `sub` ile JWT alır.

### Cüzdan format örneği (frontend localStorage)

```js
// localStorage.tl_tokens
{
  "tenants": [
    { "slug": "marketplace", "token": "eyJ…", "exp": 1716000000 },
    { "slug": "support",     "token": "eyJ…", "exp": 1716000000 }
  ]
}
```

Her tenant için ayrı backend endpoint'inden chat-token alın:

```js
async function tokenFor(tenantSlug) {
  const cached = wallet.find(t => t.slug === tenantSlug);
  if (cached && cached.exp * 1000 > Date.now() + 60_000) return cached.token;
  const fresh = await fetch(`/me/chat-token?tenant=${tenantSlug}`)
    .then(r => r.json());
  wallet = wallet.filter(t => t.slug !== tenantSlug);
  wallet.push({ slug: tenantSlug, ...fresh });
  localStorage.setItem("tl_tokens", JSON.stringify({ tenants: wallet }));
  return fresh.token;
}
```

API tarafında `iss` claim'i hangi tenant'la konuşulduğunu belirler; iki tenant da tek frontend'den paralel kullanılır.

---

## Ek: hata recovery pattern'ları

### 401 — token süresi doldu

```js
async function fetchAuthed(url, opts = {}, retried = false) {
  const res = await fetch(url, opts);
  if (res.status === 401 && !retried) {
    await refreshToken();
    return fetchAuthed(url, opts, true);
  }
  return res;
}
```

### 409 — randevu çakışması

```js
const res = await createAppointment({...});
if (res.status === 409) {
  showError("Bu zaman dilimi dolu. Başka bir saat seçin.");
}
```

### 502 — Chatwoot / Jitsi provider sorunu

Backend cevap vermiyor demektir. Toast ile bildirip kullanıcıyı yeniden denemeye çağır; bir süre sonra retry. Kalıcı 502 → operations'ı uyar.

---

## Sonraki adımlar

- [`API.md`](./API.md) — tüm endpoint detayları, schema'lar, claims
- [`CREDENTIALS.md`](../../CREDENTIALS.md) — lokal geliştirme ortamı (postgres, redis, JWT secret'ları)
- Live deneme: <http://192.168.1.163:8090/explorer/> (API Explorer) ve <http://192.168.1.163:8091/> (testbaba demo)
