function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-6 md:p-8">
      <h2 className="text-xl font-bold text-white mb-4">{title}</h2>
      <div className="space-y-4 text-sm leading-7 text-slate-300">{children}</div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen bg-[#101122] text-white px-6 py-16">
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">
            SimWork Legal
          </p>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-4">Privacy Policy</h1>
          <p className="text-slate-400 text-lg leading-relaxed">
            This Privacy Policy explains how SimWork collects, uses, and protects personal information
            when employers, candidates, and reviewers use the platform.
          </p>
          <p className="text-sm text-slate-500 mt-4">Effective date: March 24, 2026</p>
        </div>

        <Section title="Information we collect">
          <p>
            We collect account and profile data such as name, email address, profile image, and role
            within the platform. We also collect company setup details, assessment metadata, invite
            information, candidate submissions, saved evidence, scoring outputs, and activity logs needed
            to operate the service.
          </p>
          <p>
            We may also collect technical usage data such as device type, browser information, IP
            address, and session timestamps to keep the service secure and reliable.
          </p>
        </Section>

        <Section title="How we use information">
          <p>We use personal information to:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li>authenticate users and manage access to company and candidate workspaces;</li>
            <li>create and administer assessments, invite flows, and scorecards;</li>
            <li>support candidate submissions, evidence tracking, and review workflows;</li>
            <li>improve product quality, reliability, and security;</li>
            <li>respond to demo requests, support inquiries, and operational communication.</li>
          </ul>
        </Section>

        <Section title="Sharing and disclosures">
          <p>
            We do not sell personal information. We share data only with service providers, infrastructure
            partners, or authorized customer users where necessary to provide the SimWork platform. We may
            also disclose information where required by law, regulation, or a valid legal request.
          </p>
        </Section>

        <Section title="Retention and security">
          <p>
            We retain data for as long as necessary to provide the platform, meet contractual obligations,
            resolve disputes, and comply with legal requirements. We use reasonable administrative,
            technical, and organizational safeguards to protect information, but no system can guarantee
            absolute security.
          </p>
        </Section>

        <Section title="Your choices">
          <p>
            Users may request access, correction, or deletion of their information where applicable. Company
            administrators remain responsible for the assessment data they create in the platform and for
            sharing invite links with the appropriate candidates.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Questions about this Privacy Policy can be sent to{" "}
            <a href="mailto:privacy@simwork.ai" className="text-[#10B981] hover:underline">
              privacy@simwork.ai
            </a>
            .
          </p>
        </Section>
      </div>
    </main>
  );
}
