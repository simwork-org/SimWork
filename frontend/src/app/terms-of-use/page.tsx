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

export default function TermsOfUsePage() {
  return (
    <main className="min-h-screen bg-[#101122] text-white px-6 py-16">
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">
            SimWork Legal
          </p>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-4">Terms of Use</h1>
          <p className="text-slate-400 text-lg leading-relaxed">
            These Terms of Use govern access to and use of the SimWork platform by employers, candidates,
            reviewers, and other authorized users.
          </p>
          <p className="text-sm text-slate-500 mt-4">Effective date: March 24, 2026</p>
        </div>

        <Section title="Use of the platform">
          <p>
            SimWork provides scenario-based hiring assessments, candidate workspaces, invite flows, review
            tooling, and related analytics. You may use the platform only for lawful business or assessment
            purposes and only in accordance with these terms.
          </p>
        </Section>

        <Section title="Accounts and access">
          <p>
            Users must authenticate through approved sign-in methods and are responsible for maintaining the
            confidentiality of their accounts. Companies are responsible for the actions of users they
            authorize to access their workspace and assessments.
          </p>
        </Section>

        <Section title="Acceptable conduct">
          <p>You agree not to:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li>misuse the platform, interfere with its operation, or attempt unauthorized access;</li>
            <li>upload or transmit unlawful, harmful, or infringing content;</li>
            <li>use the service to violate privacy, employment, or anti-discrimination obligations;</li>
            <li>reverse engineer, scrape, or copy the service except where expressly permitted by law.</li>
          </ul>
        </Section>

        <Section title="Customer data and candidate data">
          <p>
            Employers retain responsibility for the assessments, invite links, and candidate workflows they
            create in SimWork. Candidates are responsible for the content they submit during simulations.
            SimWork may process this information to provide the contracted service and improve platform
            reliability and safety.
          </p>
        </Section>

        <Section title="Intellectual property">
          <p>
            SimWork and its related software, content, and branding remain the property of SimWork or its
            licensors. These terms do not transfer any ownership rights other than the limited right to use
            the platform in accordance with these terms.
          </p>
        </Section>

        <Section title="Disclaimers and liability">
          <p>
            The platform is provided on an &quot;as is&quot; and &quot;as available&quot; basis. To the extent
            permitted by law, SimWork disclaims implied warranties and is not liable for indirect,
            incidental, special, consequential, or punitive damages arising from use of the service.
          </p>
        </Section>

        <Section title="Changes and contact">
          <p>
            We may update these terms from time to time. Continued use of the platform after updates become
            effective constitutes acceptance of the revised terms. Questions can be sent to{" "}
            <a href="mailto:legal@simwork.ai" className="text-[#10B981] hover:underline">
              legal@simwork.ai
            </a>
            .
          </p>
        </Section>
      </div>
    </main>
  );
}
