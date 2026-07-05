import Link from "next/link";
import { Clapperboard, ArrowLeft, Shield } from "lucide-react";

export const metadata = {
  title: "Privacy Policy & GDPR — AI Director",
  description: "How Micany collects, processes, and protects your personal data, and your rights under GDPR.",
};

const EFFECTIVE_DATE = "20 June 2026";
const COMPANY = "Micany";
const PRODUCT = "AI Director";
const CONTACT_EMAIL = "mike.mediainstitute@gmail.com";
const DPO_EMAIL = "mike.mediainstitute@gmail.com";

export default function PrivacyPage() {
  return (
    <main className="relative min-h-screen">
      {/* Background */}
      <div className="pointer-events-none fixed inset-0 -z-10" style={{ background: "#02030a" }}>
        <div className="absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 40% at 50% -5%, rgba(61,169,252,0.06) 0%, transparent 65%)" }} />
      </div>

      {/* Header */}
      <header
        className="sticky top-0 z-50 border-b"
        style={{ background: "rgba(2,3,10,0.85)", backdropFilter: "blur(20px)", borderColor: "rgba(255,255,255,0.05)" }}
      >
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div
              className="h-7 w-7 rounded-md flex items-center justify-center"
              style={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border-soft)" }}
            >
              <Clapperboard className="h-3.5 w-3.5" style={{ color: "var(--color-accent-green)" }} strokeWidth={2.5} />
            </div>
            <span className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>AI Director</span>
          </Link>
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs transition-colors"
            style={{ color: "var(--color-text-secondary)" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to home
          </Link>
        </div>
      </header>

      {/* Content */}
      <article className="mx-auto max-w-4xl px-6 py-16 lg:py-24">
        {/* Title block */}
        <div className="mb-14">
          <div
            className="inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 rounded-full mb-6"
            style={{ background: "rgba(61,169,252,0.08)", border: "1px solid rgba(61,169,252,0.18)", color: "var(--color-accent-blue)" }}
          >
            <Shield className="h-3 w-3" />
            Legal · GDPR
          </div>
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight mb-4" style={{ color: "var(--color-text-primary)" }}>
            Privacy Policy &<br />GDPR Notice
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
            Effective date: {EFFECTIVE_DATE} · {COMPANY} · {PRODUCT}
          </p>
        </div>

        {/* GDPR DSR Quick-action box */}
        <div
          className="rounded-xl p-6 mb-14 flex flex-col sm:flex-row gap-4 items-start sm:items-center"
          style={{
            background: "rgba(61,169,252,0.05)",
            border: "1px solid rgba(61,169,252,0.2)",
          }}
        >
          <Shield className="h-8 w-8 flex-shrink-0" style={{ color: "var(--color-accent-blue)" }} />
          <div className="flex-1">
            <div className="text-sm font-semibold mb-1" style={{ color: "var(--color-text-primary)" }}>
              Exercise your GDPR rights
            </div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
              You can request access to, correction, deletion, or portability of your personal data at any time.
              Email our Data Protection contact with subject line <strong>DSR Request</strong>.
            </p>
          </div>
          <a
            href={`mailto:${DPO_EMAIL}?subject=DSR%20Request%20%E2%80%94%20AI%20Director&body=Please%20describe%20your%20request%3A`}
            className="flex-shrink-0 text-xs font-semibold px-4 py-2.5 rounded-lg transition-colors"
            style={{
              background: "rgba(61,169,252,0.15)",
              border: "1px solid rgba(61,169,252,0.3)",
              color: "var(--color-accent-blue)",
            }}
          >
            Submit DSR →
          </a>
        </div>

        <Prose>
          <Section title="1. Who We Are">
            <p>
              <strong>{COMPANY}</strong> is the data controller for personal data collected through <strong>{PRODUCT}</strong>. {PRODUCT} is a subsidiary product of {COMPANY}.
            </p>
            <p>
              Data Protection contact:<br />
              <a href={`mailto:${DPO_EMAIL}`}>{DPO_EMAIL}</a>
            </p>
          </Section>

          <Section title="2. What Personal Data We Collect">
            <p>We collect the following categories of personal data:</p>
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Examples</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Account data</td>
                  <td>Name, email address, profile picture</td>
                  <td>Clerk authentication provider (you provide)</td>
                </tr>
                <tr>
                  <td>Billing data</td>
                  <td>Payment method (tokenised), billing address, invoice history</td>
                  <td>Stripe (you provide)</td>
                </tr>
                <tr>
                  <td>Usage data</td>
                  <td>Pages visited, features used, API calls, job/render records</td>
                  <td>Collected automatically</td>
                </tr>
                <tr>
                  <td>Content data</td>
                  <td>Uploaded video files, generated clips, transcription text</td>
                  <td>You upload</td>
                </tr>
                <tr>
                  <td>Technical data</td>
                  <td>IP address, browser type, device identifiers, crash reports</td>
                  <td>Collected automatically</td>
                </tr>
              </tbody>
            </table>
            <p>
              We do not collect special category data (health, biometric, political, religious, or racial data) and do not process children's data (under 13).
            </p>
          </Section>

          <Section title="3. Legal Bases for Processing (GDPR Article 6)">
            <p>We process your personal data on the following lawful bases:</p>
            <ul>
              <li><strong>Contract (Art. 6(1)(b)).</strong> To provide the Service you have signed up for — account management, job processing, rendering, and delivery of outputs.</li>
              <li><strong>Legitimate interests (Art. 6(1)(f)).</strong> To prevent fraud, improve the Service, monitor security, and send product updates. We have assessed that our interests do not override your rights.</li>
              <li><strong>Legal obligation (Art. 6(1)(c)).</strong> To comply with tax, accounting, and law enforcement obligations.</li>
              <li><strong>Consent (Art. 6(1)(a)).</strong> Where we rely on consent (e.g. optional analytics cookies), you may withdraw at any time.</li>
            </ul>
          </Section>

          <Section title="4. How We Use Your Data">
            <ul>
              <li>Authenticate your identity and manage your account.</li>
              <li>Process uploaded footage through the AI Director pipeline.</li>
              <li>Bill you for your subscription via Stripe.</li>
              <li>Send transactional emails (job complete, billing receipts, security alerts).</li>
              <li>Monitor system health, detect abuse, and improve the Service.</li>
              <li>Comply with legal obligations.</li>
            </ul>
            <p>
              We do not sell, rent, or share your personal data with third parties for marketing purposes.
            </p>
          </Section>

          <Section title="5. Data Sharing and Sub-processors">
            <p>We share personal data with the following sub-processors under data processing agreements:</p>
            <ul>
              <li><strong>Clerk</strong> — identity and authentication (US, SCCs apply).</li>
              <li><strong>Stripe</strong> — payment processing (US, SCCs apply).</li>
              <li><strong>Neon</strong> — managed Postgres database (EU/US, SCCs apply).</li>
              <li><strong>Upstash</strong> — Redis job queue (EU/US, SCCs apply).</li>
              <li><strong>Cloudflare R2</strong> — object storage for uploads and exports (EU, adequacy applies).</li>
              <li><strong>Modal</strong> — serverless GPU compute for rendering (US, SCCs apply).</li>
              <li><strong>Sentry</strong> — error monitoring (US, SCCs apply).</li>
              <li><strong>Anthropic</strong> — AI plan generation (US, SCCs apply).</li>
            </ul>
            <p>
              Where sub-processors are based outside the UK/EEA, transfers are protected by Standard Contractual Clauses (SCCs) approved by the European Commission or equivalent safeguards.
            </p>
          </Section>

          <Section title="6. Data Retention">
            <ul>
              <li><strong>Account data</strong> — retained while your account is active and for 30 days after deletion.</li>
              <li><strong>Uploaded footage</strong> — retained for 90 days from upload date or until you delete it, whichever is sooner.</li>
              <li><strong>Generated clips and exports</strong> — retained for 12 months or until you delete them.</li>
              <li><strong>Billing records</strong> — retained for 7 years to comply with UK/EU accounting law.</li>
              <li><strong>Usage logs</strong> — anonymised after 12 months; raw logs deleted after 90 days.</li>
            </ul>
          </Section>

          <Section title="7. Your Rights Under GDPR">
            <p>
              If you are located in the European Economic Area (EEA), United Kingdom, or Switzerland, you have the following rights regarding your personal data:
            </p>
            <ul>
              <li><strong>Right of access (Art. 15).</strong> Request a copy of all personal data we hold about you.</li>
              <li><strong>Right to rectification (Art. 16).</strong> Request correction of inaccurate or incomplete data.</li>
              <li><strong>Right to erasure / "right to be forgotten" (Art. 17).</strong> Request deletion of your data where we no longer have a lawful basis to process it.</li>
              <li><strong>Right to restriction (Art. 18).</strong> Request that we restrict processing while a dispute is resolved.</li>
              <li><strong>Right to data portability (Art. 20).</strong> Receive your data in a machine-readable format (JSON / CSV).</li>
              <li><strong>Right to object (Art. 21).</strong> Object to processing based on legitimate interests; we will cease unless we demonstrate compelling legitimate grounds.</li>
              <li><strong>Right to withdraw consent.</strong> Where processing is consent-based, withdraw consent at any time without affecting prior processing.</li>
              <li><strong>Right to lodge a complaint.</strong> You have the right to lodge a complaint with your national supervisory authority (UK: ICO; EU: your local DPA).</li>
            </ul>
            <p>
              To exercise any of these rights, submit a Data Subject Request (DSR):
            </p>
            <p>
              <a
                href={`mailto:${DPO_EMAIL}?subject=DSR%20Request%20%E2%80%94%20AI%20Director&body=Please%20describe%20your%20request%3A`}
              >
                {DPO_EMAIL} (subject: DSR Request)
              </a>
            </p>
            <p>
              We will respond within <strong>30 days</strong> of receipt of a verified request, as required by GDPR Article 12. Identity verification may be required before processing your request.
            </p>
          </Section>

          <Section title="8. Cookies and Tracking">
            <p>
              We use the following cookies and similar technologies:
            </p>
            <ul>
              <li><strong>Strictly necessary cookies</strong> — Clerk session token, CSRF protection. Cannot be disabled.</li>
              <li><strong>Functional cookies</strong> — Your theme and UI preferences. Disabled on request.</li>
              <li><strong>Analytics (optional)</strong> — Aggregated usage metrics. We do not use Google Analytics. No third-party ad tracking.</li>
            </ul>
            <p>
              You can manage cookie preferences via your browser settings. Disabling strictly necessary cookies will prevent you from signing in.
            </p>
          </Section>

          <Section title="9. Security">
            <p>
              We apply industry-standard security controls including:
            </p>
            <ul>
              <li>TLS 1.3 for all data in transit.</li>
              <li>AES-256 encryption for data at rest (Neon, Cloudflare R2).</li>
              <li>Ed25519 provenance signing on all exported clips.</li>
              <li>Role-based access control; no cross-tenant data access.</li>
              <li>Automated dependency scanning and security patching.</li>
            </ul>
            <p>
              In the event of a personal data breach affecting your rights and freedoms, we will notify the relevant supervisory authority within 72 hours and affected users without undue delay, as required by GDPR Article 33–34.
            </p>
          </Section>

          <Section title="10. International Transfers">
            <p>
              Some of our sub-processors are based in the United States. Where personal data is transferred outside the UK/EEA, we rely on Standard Contractual Clauses (SCCs) as the appropriate transfer mechanism. A list of current sub-processors and their locations is available on request.
            </p>
          </Section>

          <Section title="11. Changes to This Policy">
            <p>
              We may update this Privacy Policy from time to time. We will notify you of material changes by email or in-product notice at least 14 days before changes take effect. The "Effective date" at the top of this page will always reflect the current version.
            </p>
          </Section>

          <Section title="12. Contact and Complaints">
            <p>
              For privacy queries, Data Subject Requests, or complaints:
            </p>
            <p>
              <strong>Micany — AI Director</strong><br />
              Data Protection contact: <a href={`mailto:${DPO_EMAIL}`}>{DPO_EMAIL}</a>
            </p>
            <p>
              If you believe your rights have been violated and we have not resolved your concern, you have the right to lodge a complaint with:
            </p>
            <ul>
              <li><strong>UK:</strong> Information Commissioner's Office (ICO) — <a href="https://ico.org.uk" target="_blank" rel="noopener noreferrer">ico.org.uk</a></li>
              <li><strong>EU:</strong> Your national Data Protection Authority — <a href="https://edpb.europa.eu/about-edpb/about-edpb/members_en" target="_blank" rel="noopener noreferrer">edpb.europa.eu</a></li>
            </ul>
          </Section>
        </Prose>

        {/* Footer link */}
        <div className="mt-16 pt-8 flex items-center justify-between" style={{ borderTop: "1px solid var(--color-border-soft)" }}>
          <Link
            href="/terms"
            className="text-sm transition-colors"
            style={{ color: "var(--color-text-secondary)" }}
          >
            ← Terms of Use
          </Link>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>© {new Date().getFullYear()} Micany</span>
        </div>
      </article>
    </main>
  );
}

/* ── Layout helpers ── */

function Prose({ children }: { children: React.ReactNode }) {
  return <div className="space-y-10">{children}</div>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2
        className="text-lg font-semibold mb-4 pb-2"
        style={{ color: "var(--color-text-primary)", borderBottom: "1px solid var(--color-border-soft)" }}
      >
        {title}
      </h2>
      <div
        className="space-y-4 text-sm leading-relaxed [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:opacity-80 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2 [&_table]:w-full [&_table]:border-collapse [&_th]:text-left [&_th]:text-xs [&_th]:uppercase [&_th]:tracking-widest [&_th]:pb-2 [&_td]:py-2 [&_td]:pr-4 [&_td]:align-top [&_tr]:border-b"
        style={{
          color: "var(--color-text-secondary)",
          ["--tw-prose-td-border" as string]: "var(--color-border-soft)",
        }}
      >
        {children}
      </div>
    </section>
  );
}
