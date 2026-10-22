import React from 'react';

const UPDATED = '22 October 2026';
const CONTACT = 'support@luminaiq.fun';

const Section = ({ title, children }) => (
    <section className="mt-8">
        <h2 className="text-xl font-bold text-[#4A3B32]">{title}</h2>
        <div className="mt-2 space-y-3 leading-relaxed text-[#5a4a42]">{children}</div>
    </section>
);

const Shell = ({ title, children }) => (
    <div className="min-h-screen bg-[#FDF6F0] px-5 py-10" style={{ paddingTop: 'calc(var(--sat) + 2.5rem)' }}>
        <article className="mx-auto max-w-2xl rounded-3xl bg-white p-6 shadow-sm md:p-10">
            <button onClick={() => (window.history.length > 1 ? window.history.back() : window.location.assign('/'))} className="text-sm font-semibold text-[#C8A288]">← Back</button>
            <h1 className="mt-4 text-3xl font-extrabold text-[#4A3B32]">{title}</h1>
            <p className="mt-1 text-sm text-[#8a6a5c]">Last updated {UPDATED}</p>
            {children}
            <p className="mt-10 text-sm text-[#8a6a5c]">Questions? Email <a className="font-semibold text-[#C8A288]" href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
        </article>
    </div>
);

export const Privacy = () => (
    <Shell title="Privacy Policy">
        <p className="mt-6 leading-relaxed text-[#5a4a42]">
            LuminaIQ (the website at luminaiq.fun and the LuminaIQ app) helps you study from your own books and notes.
            This policy explains what we collect, why, and the choices you have.
        </p>
        <Section title="What we collect">
            <p><b>Account details:</b> your email address and name, and your Google profile name and picture if you sign in with Google.</p>
            <p><b>Your study material:</b> the files and text you upload, and the text we extract from them (including text read from scanned pages).</p>
            <p><b>What you make and do:</b> notes, flashcards, quizzes, chat messages, answers, scores, streaks, XP and your settings.</p>
            <p><b>Payments:</b> if you buy a plan on the website, our payment provider (Razorpay) processes your payment. We keep the plan, amount and payment reference, never your card or bank details.</p>
            <p><b>Basic usage data:</b> anonymous page-view and performance statistics on the website, and crash or error logs, to keep the service working.</p>
        </Section>
        <Section title="How we use it">
            <p>To provide the service: reading your files, building your study tools, answering your questions about your material, tracking your progress and sending study reminders you turn on. We do not sell your data and we do not use your uploads to advertise to you.</p>
        </Section>
        <Section title="Services that process your data for us">
            <p>To run LuminaIQ we use trusted providers that process data on our behalf: Supabase (accounts, database and file storage), Qdrant (search index of your material), Render and Vercel (hosting), AI model providers such as Amazon Web Services (Bedrock) for answers and generated study material, Google Cloud Vision and our own OCR service for reading scanned pages, an embeddings provider for search, and Razorpay for payments. They receive only what they need to do that job.</p>
        </Section>
        <Section title="Sharing">
            <p>Your books and study data are private to your account. If you join a class through an institution, your teacher can see your class progress. We share data only with the providers above, or when the law requires it.</p>
        </Section>
        <Section title="Keeping and deleting your data">
            <p>We keep your data while your account exists. You can delete a file or a book at any time, and you can delete your whole account in the app (You → Delete account) or by emailing us. Deleting your account permanently removes your files, extracted text, search index, study data and login. Payment records are kept where the law requires it.</p>
        </Section>
        <Section title="Security">
            <p>Data is sent over encrypted connections (HTTPS) and stored with access controls so only your account can reach your files.</p>
        </Section>
        <Section title="Children">
            <p>LuminaIQ is meant for learners aged 13 and over. If you are under the age required to consent in your country, use it with a parent's or guardian's permission.</p>
        </Section>
        <Section title="Notifications">
            <p>The app sends a daily study reminder only if you turn it on, and you can turn it off at any time in the app or in your phone's settings.</p>
        </Section>
        <Section title="Changes">
            <p>If we change this policy we will update the date above, and tell you in the app for important changes.</p>
        </Section>
    </Shell>
);

export const Terms = () => (
    <Shell title="Terms of Use">
        <Section title="Using LuminaIQ">
            <p>LuminaIQ gives you study tools built from material you upload. By creating an account you agree to these terms. You must be 13 or older, or have a parent's or guardian's permission.</p>
        </Section>
        <Section title="Your content">
            <p>You keep all rights to what you upload. You confirm you have the right to use it for your own study. You give us permission to store and process it only to provide the service to you. Don't upload material that is illegal or that you have no right to use.</p>
        </Section>
        <Section title="AI-generated material">
            <p>Answers, notes, questions and other material are generated by AI from your content. They can contain mistakes. Check important facts against your sources before relying on them, for example in an exam.</p>
        </Section>
        <Section title="Plans and limits">
            <p>Free accounts have daily and monthly limits. Paid plans bought on the website renew as described at checkout until cancelled. You can cancel at any time; access continues until the end of the paid period.</p>
        </Section>
        <Section title="Acceptable use">
            <p>Don't misuse the service: no attempts to break, overload or reverse-engineer it, no automated scraping, and no sharing your account.</p>
        </Section>
        <Section title="Ending your account">
            <p>You can delete your account at any time from the app. We may suspend accounts that break these terms.</p>
        </Section>
        <Section title="Liability">
            <p>LuminaIQ is provided as is. To the extent the law allows, we are not liable for indirect losses, or for results based on AI-generated material.</p>
        </Section>
    </Shell>
);
