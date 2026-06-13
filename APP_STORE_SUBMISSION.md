# FriedSports — App Store Submission Kit

Practical checklist + copy-paste metadata for App Store Connect. Updated 2026-06-13.

---

## 0. Build prep (do this after pulling latest)

The push plugin was removed and a privacy manifest was added, so the iOS project
must be regenerated:

```bash
npm install                # drops @capacitor/push-notifications
npx cap sync ios           # regenerates Podfile.lock + pods (no more push pod)
```

Then in Xcode **once**:
- Add `ios/App/App/PrivacyInfo.xcprivacy` to the **App target** (File → Add Files
  to "App"… → check "App" under Target Membership). Capacitor doesn't auto-add it.
- Confirm **Signing & Capabilities** has **no** "Push Notifications" capability
  (we're not using push yet).
- Set **Version** (e.g. 1.0.0) and **Build** (e.g. 1).

---

## 1. Reviewer login (was the #1 rejection risk — now solved)

Login no longer requires the emailed OTP code — **email + password signs in
directly** (the OTP block in `app/routes/auth.py` is commented out, not deleted).
Apple's reviewer can now log in with credentials you provide.

**To do:** create one real review account in production, then put this in
App Store Connect → App Review Information → Sign-In Required:

```
Username: review@friedsports.com
Password: <set a strong one>
Notes: Email + password signs you straight in (no email code needed). After
login, tap "Groups" to create a group, then "+ Start Incident" to open a thread
and post a message. Report a message via the ⚑ icon; block a user from the
friends list ⋯ menu.
```

> Make sure that account is in at least one group with an active thread so the
> reviewer sees a populated app, not empty states.

---

## 2. Guideline 4.2 (Minimum Functionality) — what it means, plainly

**The rule:** Apple rejects apps that are "just a website in a wrapper" — i.e.
a WebView pointed at your site with nothing a mobile browser couldn't already do.

**Why we're exposed:** `capacitor.config.json` has `server.url =
https://www.friedsports.com`, so the app loads the live site in a WebView. That
is the single most common 4.2 trigger.

**This is NOT a one-line code fix** — it's about the app offering native value.

**Path A is now implemented** (the lower-effort route): the app uses real native
iOS capabilities a website can't, via `app/static/js/native.js`:
- **Native share sheet** on group invite links and shareable receipts
  (`@capacitor/share`). On the receipt page this also fixes the WKWebView
  clipboard restriction — a real native win, not cosmetic.
- **Haptic feedback** on core actions — sending a message, voting, reacting
  (`@capacitor/haptics`).
- Plus the existing native splash screen, status-bar styling, and app icon.

All of it is guarded: on the mobile web it falls back to the Web Share API /
clipboard and haptics are no-ops, so the same code ships everywhere.

**If 4.2 still comes back** after this, the stronger fallback is **Path B**:
point Capacitor at a bundled `webDir` instead of the remote `server.url` so the
binary ships real assets and talks to the `/api` endpoints. More work, but it's
the shape Apple prefers. Start with Path A — it's in the build now.

**Honest caveat:** 4.2 is ultimately the reviewer's judgment call. Native share +
haptics materially reduce the "it's just a website" risk, but nothing guarantees
a pass. If rejected, reply in Resolution Center pointing to the native features,
or move to Path B.

---

## 3. App metadata (paste into App Store Connect)

**Name:** FriedSports
**Subtitle (30 char):** Sports trash talk, organized
**Promotional text:** Keep the receipts. Settle who was right when their team chokes.

**Description:**
```
FriedSports is where friend groups talk trash about sports — organized.

When someone's team blows it, file an "incident," start a thread, and let the
group weigh in: Confirm, Dismiss, or Redeemed. Keep the receipts so there's a
record of who called it and who choked.

• Private groups for your friends
• Incident threads with group voting
• Reactions, unread tracking, and activity
• Friends, shared groups, and standings

FriedSports is for good-natured ribbing between friends. Harassment, hate
speech, and threats are not allowed — report or block anyone who crosses the
line, and our team reviews reports.
```

**Keywords (100 char):** `sports,trash talk,friends,group chat,banter,fantasy,receipts,smack talk,fans,rivalry`

**Support URL:** https://www.friedsports.com/support
**Marketing URL:** https://www.friedsports.com
**Privacy Policy URL:** https://www.friedsports.com/privacy

---

## 4. Age rating (answer in App Store Connect questionnaire)

This is a UGC app with crude/mature humor → expect **17+**. Answer honestly:

- Profanity or Crude Humor: **Frequent/Intense**
- Mature/Suggestive Themes: **Infrequent/Mild**
- Horror/Fear, Violence (cartoon/realistic), Sexual Content, Nudity, Gambling,
  Alcohol/Tobacco/Drugs, Medical, Contests: **None**
- **Unrestricted Web Access: No** (the app is scoped to friedsports.com)
- **User-Generated Content: Yes** → this triggers the questions about
  moderation; you can answer that the app has reporting, blocking, and a
  published code of conduct (all true — see §6).

---

## 5. App Privacy "nutrition label" (App Store Connect → App Privacy)

Mirror the `PrivacyInfo.xcprivacy` we ship. **No tracking. No third-party ads/analytics.**
Declare these as **collected, linked to the user, used for App Functionality only:**

| Data type | Linked | Tracking | Purpose |
|---|---|---|---|
| Email address | Yes | No | App Functionality |
| Name | Yes | No | App Functionality |
| User ID | Yes | No | App Functionality |
| Other User Content (messages) | Yes | No | App Functionality |

"Data Used to Track You": **None.** "Data Linked to You": the four above.

---

## 6. UGC compliance (Guideline 1.2) — already implemented

These are the things Apple checks for a user-generated-content app. All shipped:

- **Report content:** ⚑ on each message → category action sheet → backend.
- **Block users:** friends list ⋯ menu and report sheet; blocked users' content
  is hidden both ways.
- **Moderation:** admin queue at `/admin/reports` to delete content / dismiss.
- **EULA / code of conduct:** required agreement at signup with zero-tolerance
  language; published Terms (`/terms`) and Privacy (`/privacy`).
- **Account deletion:** Settings → Delete Account (in-app, permanent).

---

## 7. Final pre-submit checklist

- [ ] `npx cap sync ios` run; Podfile.lock has no CapacitorPushNotifications
- [ ] PrivacyInfo.xcprivacy added to the App target in Xcode
- [ ] No Push Notifications capability in Signing & Capabilities
- [ ] Review account created in prod + credentials in App Review notes
- [ ] Screenshots for required device sizes (6.7" + 6.5" iPhone at minimum)
- [ ] Age rating completed (17+)
- [ ] App Privacy answers match §5
- [ ] Support/Marketing/Privacy URLs reachable (they are: /support, /, /privacy)
- [ ] Decide Path A vs B for 4.2 (§2)
```
