import Link from "next/link";
import { Clapperboard, ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Terms of Use — AI Director",
  description: "Terms of Use for AI Director, a Micany subsidiary product.",
};

const EFFECTIVE_DATE = "20 June 2026";
const COMPANY = "Micany";
const PRODUCT = "AI Director";
const CONTACT_EMAIL = "mike.mediainstitute@gmail.com";

export default function TermsPage() {
  return (
    <main className="relative min-h-screen">
      {/* Background */}
      <div className="pointer-events-none fixed inset-0 -z-10" style={{ background: "#02030a" }}>
        <div className="absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 40% at 50% -5%, rgba(0,230,161,0.07) 0%, transparent 65%)" }} />
      </div>

      {/* Header */}
      <header
        className="sticky top-0 z-50 border-b"
        style={{ background: "rgba(2,3,10,0.85)", backdropFilter: "blur(20px)", borderColor: "rgba(255,255,255,0.05)" }}
      >
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
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
            className="inline-block text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 rounded-full mb-6"
            style={{ background: "rgba(0,230,161,0.08)", border: "1px solid rgba(0,230,161,0.18)", color: "var(--color-accent-green)" }}
          >
            Legal
          </div>
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight mb-4" style={{ color: "var(--color-text-primary)" }}>
            Terms of Use
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
            Effective date: {EFFECTIVE_DATE} · {COMPANY} · {PRODUCT}
          </p>
        </div>

        <Prose>
          <Section title="1. Acceptance of Terms">
            <p>
              By accessing or using <strong>{PRODUCT}</strong> (the "Service"), operated by <strong>{COMPANY}</strong> ("we", "us", "our"), you agree to be bound by these Terms of Use ("Terms"). If you are using the Service on behalf of an organisation, you represent that you have authority to bind that organisation to these Terms, and "you" refers to that organisation.
            </p>
            <p>
              If you do not agree to these Terms, you must not access or use the Service.
            </p>
          </Section>

          <Section title="2. Description of Service">
            <p>
              {PRODUCT} is an AI-powered sports video editing and clip-generation platform that analyses match footage, ranks moments using structured intelligence, and produces platform-ready video exports. The Service is operated as a subsidiary product of {COMPANY}.
            </p>
          </Section>

          <Section title="3. Eligibility">
            <p>
              You must be at least 18 years old and capable of forming a legally binding contract to use the Service. The Service is not intended for use by persons under 13 years of age. We do not knowingly collect personal data from children under 13.
            </p>
          </Section>

          <Section title="4. Account Registration">
            <p>
              To access most features you must create an account via Clerk authentication. You are responsible for maintaining the confidentiality of your credentials and for all activity under your account. You must notify us immediately of any unauthorised use at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
            <p>
              We reserve the right to suspend or terminate accounts that violate these Terms or that we reasonably believe pose a security risk.
            </p>
          </Section>

          <Section title="5. Acceptable Use">
            <p>You agree not to:</p>
            <ul>
              <li>Upload content to which you do not own or hold a valid licence for all intellectual property rights, including video footage, audio, and branding.</li>
              <li>Use the Service to produce content that infringes third-party intellectual property rights, including but not limited to broadcaster, league, or club rights.</li>
              <li>Attempt to reverse-engineer, decompile, or extract the source code of any part of the Service.</li>
              <li>Use automated means (bots, scrapers) to access the Service outside of the documented API.</li>
              <li>Upload content that is unlawful, harmful, defamatory, obscene, or otherwise objectionable.</li>
              <li>Circumvent any rate limits, access controls, or security measures.</li>
              <li>Resell or sublicense access to the Service without our written consent.</li>
            </ul>
          </Section>

          <Section title="6. Intellectual Property">
            <p>
              <strong>Our IP.</strong> The Service, including its software, algorithms, design, trademarks (including the AI Director and Micany names and logos), and all content we produce, is owned by {COMPANY} or our licensors and is protected by copyright, trade secret, and other laws. You receive a limited, non-exclusive, non-transferable licence to use the Service solely as permitted by these Terms.
            </p>
            <p>
              <strong>Your content.</strong> You retain all rights in footage and materials you upload ("User Content"). By uploading User Content, you grant us a limited, worldwide, royalty-free licence to process, transcode, analyse, and store your User Content solely to provide the Service to you. We do not claim ownership of your User Content.
            </p>
            <p>
              <strong>Output clips.</strong> AI-generated output clips produced from your User Content are owned by you, subject to any third-party rights in the underlying footage.
            </p>
          </Section>

          <Section title="7. Subscriptions and Billing">
            <p>
              Paid plans are billed monthly via Stripe. Prices are shown exclusive of applicable taxes. Taxes are calculated at checkout based on your billing address.
            </p>
            <p>
              Subscriptions auto-renew unless cancelled at least 24 hours before the renewal date. Refunds are not provided for unused portions of a billing period except where required by applicable law.
            </p>
            <p>
              We reserve the right to change pricing with 30 days' notice. Continued use after the effective date of a price change constitutes acceptance.
            </p>
          </Section>

          <Section title="8. Data and Privacy">
            <p>
              Our collection, use, and disclosure of personal data is governed by our <Link href="/privacy">Privacy Policy & GDPR Notice</Link>. By using the Service you consent to those practices.
            </p>
          </Section>

          <Section title="9. Availability and Modifications">
            <p>
              We provide the Service on a commercially reasonable basis but do not guarantee uninterrupted or error-free operation. We may modify, suspend, or discontinue any part of the Service at any time. We will endeavour to provide reasonable notice of material changes.
            </p>
          </Section>

          <Section title="10. Disclaimers">
            <p>
              THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, {COMPANY.toUpperCase()} DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
            </p>
            <p>
              We do not warrant that AI-generated scores, rankings, or clip selections are accurate, complete, or suitable for any particular purpose. All AI outputs should be reviewed by a human before publication.
            </p>
          </Section>

          <Section title="11. Limitation of Liability">
            <p>
              TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, {COMPANY.toUpperCase()} AND ITS OFFICERS, DIRECTORS, EMPLOYEES, AND AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING OUT OF OR RELATED TO YOUR USE OF THE SERVICE.
            </p>
            <p>
              OUR TOTAL LIABILITY TO YOU FOR ANY CLAIM ARISING OUT OF OR RELATED TO THESE TERMS OR THE SERVICE SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNTS YOU PAID TO US IN THE 12 MONTHS PRECEDING THE CLAIM OR (B) £100.
            </p>
          </Section>

          <Section title="12. Indemnification">
            <p>
              You agree to indemnify and hold harmless {COMPANY}, its subsidiaries, officers, directors, employees, and agents from and against any claims, liabilities, damages, losses, and expenses (including reasonable legal fees) arising out of or in any way connected with: (a) your access to or use of the Service; (b) your User Content; or (c) your violation of these Terms or any applicable law.
            </p>
          </Section>

          <Section title="13. Governing Law and Dispute Resolution">
            <p>
              These Terms are governed by the laws of England and Wales, without regard to conflict-of-law principles. Any disputes shall be submitted to the exclusive jurisdiction of the courts of England and Wales, except where mandatory consumer protection laws in your country of residence provide otherwise.
            </p>
          </Section>

          <Section title="14. Changes to Terms">
            <p>
              We may update these Terms from time to time. We will notify you of material changes by email or in-product notice at least 14 days before the changes take effect (7 days for minor updates). Your continued use of the Service after the effective date constitutes acceptance of the revised Terms.
            </p>
          </Section>

          <Section title="15. Contact">
            <p>
              For questions about these Terms, contact us at:<br />
              <strong>Micany — AI Director</strong><br />
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </p>
          </Section>
        </Prose>

        {/* Footer link */}
        <div className="mt-16 pt-8 flex items-center justify-between" style={{ borderTop: "1px solid var(--color-border-soft)" }}>
          <Link
            href="/privacy"
            className="text-sm transition-colors"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Privacy Policy & GDPR →
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
        className="space-y-4 text-sm leading-relaxed [&_a]:underline [&_a]:underline-offset-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {children}
      </div>
    </section>
  );
}
