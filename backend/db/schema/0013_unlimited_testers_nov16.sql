-- Testers with unlimited access (no plan limits), as on 2026-11-16.
-- is_unlimited() joins on lower(app_users.email), so access applies as soon as
-- each person signs in, including anyone who hasn't signed up yet.
-- ON CONFLICT keeps existing rows (and their notes) unchanged.
INSERT INTO unlimited_access (email, note) VALUES
    ('muzzainu.bbaa@gmail.com', 'play tester'),
    ('a.sanjayram262005@gmail.com', 'play tester'),
    ('ai.genrec@gmail.com', 'play tester'),
    ('alagammai0112@gmail.com', 'play tester'),
    ('balaraman25@gmail.com', 'play tester'),
    ('dhamunikita@gmail.com', 'play tester'),
    ('dhanyashree2297@gmail.com', 'play tester'),
    ('harishinisundar03@gmail.com', 'play tester'),
    ('jaisamyukth2@gmail.com', 'play tester'),
    ('jaisamyukth@gmail.com', 'play tester'),
    ('janadevaraj21@gmail.com', 'play tester'),
    ('jeyram2009@gmail.com', 'play tester'),
    ('kavinya41@gmail.com', 'play tester'),
    ('keerthi141985@gmail.com', 'play tester'),
    ('mani2005nkl@gmail.com', 'play tester'),
    ('manjushrithurai@gmail.com', 'play tester'),
    ('maryamnibras.s@gmail.com', 'play tester'),
    ('nirmallr325@gmail.com', 'play tester'),
    ('npoornachandrika@gmail.com', 'play tester'),
    ('raajashanmuga@gmail.com', 'play tester'),
    ('shafiqhomelife@gmail.com', 'play tester'),
    ('shyamnathsankar123@gmail.com', 'play tester'),
    ('sureshkako@gmail.com', 'play tester'),
    ('suryaprasath41@gmail.com', 'play tester'),
    ('tamilselvanrathinasamy7@gmail.com', 'play tester'),
    ('umaramesh02@gmail.com', 'play tester')
ON CONFLICT (email) DO NOTHING;
