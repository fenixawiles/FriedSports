import { Link, useLocation, useNavigate } from 'react-router-dom'

function BackLink() {
  const navigate = useNavigate()
  return (
    <button type="button" className="page-back-btn" onClick={() => navigate(-1)}>
      ‹ Back
    </button>
  )
}

function PrivacyPolicy() {
  return (
    <>
      <h1 className="legal-title">Privacy Policy</h1>
      <p className="legal-effective">Effective: May 2025</p>

      <p className="legal-intro">
        FriedSports is a private social platform for sports trash talk between
        friends. This policy explains what data we collect, how we use it, and
        your rights.
      </p>

      <div className="legal-section">
        <h2>What We Collect</h2>
        <ul>
          <li><strong>Account information</strong> — your email address, first name, last name, and username when you create an account.</li>
          <li><strong>Profile preferences</strong> — your favorite sports teams and display name preference.</li>
          <li><strong>Content you create</strong> — messages, reactions, and threads you post within groups.</li>
          <li><strong>Usage data</strong> — standard server logs including IP addresses and timestamps when you access the service.</li>
        </ul>
      </div>

      <div className="legal-section">
        <h2>How We Use It</h2>
        <ul>
          <li>To authenticate you and maintain your session.</li>
          <li>To display your name and content to other members of your groups.</li>
          <li>To operate and improve the service.</li>
        </ul>
        <p>We do not sell your data. We do not share your data with third parties except as required to operate the service.</p>
      </div>

      <div className="legal-section">
        <h2>Data Storage</h2>
        <p>Your data is stored in a PostgreSQL database hosted by Neon and served via Railway, both US-based cloud providers.</p>
      </div>

      <div className="legal-section">
        <h2>Your Rights</h2>
        <ul>
          <li><strong>Access</strong> — you can view all data associated with your account in Settings.</li>
          <li><strong>Correction</strong> — you can update your name, email, and preferences in Settings at any time.</li>
          <li><strong>Deletion</strong> — you can permanently delete your account and all associated data from Settings. Deletion is immediate and irreversible.</li>
        </ul>
      </div>

      <div className="legal-section">
        <h2>Cookies</h2>
        <p>We use session cookies to keep you logged in. No tracking cookies, no advertising cookies.</p>
      </div>

      <div className="legal-section">
        <h2>Children</h2>
        <p>FriedSports is intended for users 17 and older due to user-generated content. We do not knowingly collect data from anyone under 13.</p>
      </div>

      <div className="legal-section">
        <h2>Contact</h2>
        <p>Questions about this policy or requests regarding your data: <a href="mailto:privacy@friedsports.com">privacy@friedsports.com</a></p>
      </div>

      <p className="legal-cross-link">
        <Link to="/legal/terms">Terms of Service</Link>
      </p>
    </>
  )
}

function TermsOfService() {
  return (
    <>
      <h1 className="legal-title">Terms of Service</h1>
      <p className="legal-effective">Effective: May 2025</p>

      <p className="legal-intro">
        By creating an account on FriedSports, you agree to these terms. If you
        do not agree, do not use the service.
      </p>

      <div className="legal-section">
        <h2>The Service</h2>
        <p>FriedSports is a private platform that lets friend groups create trash-talk threads when someone's sports team loses. It is meant to be fun. It is not meant to be used for harassment.</p>
      </div>

      <div className="legal-section">
        <h2>Your Account</h2>
        <ul>
          <li>You must be 13 or older to create an account; 17+ is recommended because this app has user-generated content.</li>
          <li>You are responsible for keeping your password secure.</li>
          <li>You are responsible for all activity that happens under your account.</li>
          <li>You can delete your account at any time from Settings. Deletion removes your data permanently.</li>
        </ul>
      </div>

      <div className="legal-section">
        <h2>Community Guidelines</h2>
        <p>FriedSports is for sports trash talk between people who know each other. It is not for:</p>
        <ul>
          <li>Targeted harassment or threats of real-world harm.</li>
          <li>Content involving minors.</li>
          <li>Hate speech based on race, ethnicity, religion, gender, sexuality, or disability.</li>
          <li>Doxxing or sharing someone's private real-world information without consent.</li>
          <li>Spam or any form of commercial solicitation.</li>
        </ul>
        <p>Violating these guidelines can result in removal from groups or account termination.</p>
      </div>

      <div className="legal-section">
        <h2>Your Content</h2>
        <p>You own what you post. By posting, you grant FriedSports a license to store and display it to the members of your groups.</p>
        <p>We do not claim ownership of your content and we do not use it for advertising.</p>
      </div>

      <div className="legal-section">
        <h2>Disclaimers</h2>
        <p>FriedSports is provided as is. We are not responsible for content posted by users. We do not guarantee uptime.</p>
      </div>

      <div className="legal-section">
        <h2>Changes to These Terms</h2>
        <p>We may update these terms occasionally. Continued use of the service after changes constitutes acceptance.</p>
      </div>

      <div className="legal-section">
        <h2>Contact</h2>
        <p><a href="mailto:hello@friedsports.com">hello@friedsports.com</a></p>
      </div>

      <p className="legal-cross-link">
        <Link to="/legal/privacy">Privacy Policy</Link>
      </p>
    </>
  )
}

export default function Legal() {
  const location = useLocation()
  const isTerms = location.pathname.includes('terms')

  return (
    <div className="legal-container">
      <div className="page-back-wrap">
        <BackLink />
      </div>
      <div className="legal-card">
        {isTerms ? <TermsOfService /> : <PrivacyPolicy />}
      </div>
    </div>
  )
}
