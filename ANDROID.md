# Lumina IQ Android app (Google Play)

The app is the Lumina IQ web app packaged with [Capacitor](https://capacitorjs.com) 8:
`frontend/android/` is the native project, `frontend/capacitor.config.json` its config.
App ID **`fun.luminaiq.app`** (permanent once published), targets Android 16 (API 36),
runs on Android 7+ (API 24).

## How it's built

GitHub Actions (`.github/workflows/android.yml`) builds on every push to
`jaisamyukth-changes` that touches `frontend/`, or on demand (Actions → *Android app* →
*Run workflow*, where you can also set the version name). Each run's **Artifacts** contain:

| File | Use |
|---|---|
| `LuminaIQ-debug.apk` | Install on any phone to test (allow "install unknown apps") |
| `LuminaIQ-release.apk` | Signed release APK *(only once signing is set up)* |
| `LuminaIQ-release.aab` | Signed bundle you upload to Google Play *(only once signing is set up)* |

The build points the app at the **test backend** by default. For the production app set
the repository variable `ANDROID_API_URL` to the production backend URL
(`https://<prod-backend>/api/v1`).

## What you need to do

### 1. Create your upload key (once, keep it forever)

```bash
keytool -genkeypair -v -keystore luminaiq-upload.jks -alias luminaiq \
  -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 luminaiq-upload.jks > keystore.b64   # macOS: base64 -i luminaiq-upload.jks
```

Back up `luminaiq-upload.jks` and its passwords somewhere safe. Never commit them.
GitHub → repository → Settings → Secrets and variables → Actions → **New repository secret**:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | contents of `keystore.b64` |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | `luminaiq` |
| `ANDROID_KEY_PASSWORD` | key password |

The next build produces the signed `.aab`.

### 2. Allow the app's Google sign-in redirect

Supabase Dashboard → Authentication → URL Configuration → **Redirect URLs** → add
`fun.luminaiq.app://login-callback`. (In the app, Google sign-in opens in the system
browser and returns through this link; email + password and email codes work without it.)

### 3. Publish a privacy policy

Google Play requires a public privacy-policy URL (and so does Razorpay). The site has none
yet; add one (e.g. `https://luminaiq.fun/privacy`) covering: account data (email, name),
uploaded documents and their text, study progress, AI processing by third-party model
providers, payments via Razorpay, and how to delete an account.

### 4. Google Play Console

1. Create a developer account (one-time US$25) at play.google.com/console.
2. **Create app** → name *Lumina IQ*, app, free.
3. Store listing: short description (the pitch: *"Turn any textbook into the shortest
   path to exam-ready, even overnight."*), full description, icon 512×512
   (`frontend/assets/logo.png` resized), feature graphic 1024×500, at least 2 phone
   screenshots.
4. App content: privacy policy URL (step 3), ads: none, content rating questionnaire,
   target audience (13+ recommended; under-13 triggers the Families policy),
   **Data safety**: collects email, name, user-uploaded files, app activity; encrypted in
   transit; users can request deletion.
5. Testing → Internal testing → create release → upload `LuminaIQ-release.aab` → add
   testers' emails. Then promote to Closed → Production. New personal developer accounts
   must run a closed test with at least 12 testers for 14 days before production.
6. Let Google manage the app signing key (Play App Signing, default). Your upload key from
   step 1 only signs uploads.

## Payments and Google Play policy

Google Play requires its own billing system for digital subscriptions bought *inside* the
app. So in the Android app the purchase buttons, Pricing checkout, Exam Night Pass, seat
checkout and upgrade prompts are hidden (`isNativeApp()` in `src/utils/platform.js`).
Plans bought on the website work in the app automatically (same account).

To sell inside the app later, either integrate Google Play Billing, or enrol in Google's
*User Choice Billing* for India to offer Razorpay alongside Play Billing. Both need code
and Play Console setup; ask before enabling purchases in the app.

## Local development (optional)

```bash
cd frontend
npm run build && npx cap sync android
npx cap open android          # opens Android Studio; Run ▶ on a device/emulator
```

Local release signing: create `frontend/android/keystore.properties` (git-ignored):

```
storeFile=/absolute/path/luminaiq-upload.jks
storePassword=…
keyAlias=luminaiq
keyPassword=…
```

Icons and splash screens are generated from `frontend/assets/logo.png` and
`frontend/assets/splash.png` with `npx @capacitor/assets generate --android`.
