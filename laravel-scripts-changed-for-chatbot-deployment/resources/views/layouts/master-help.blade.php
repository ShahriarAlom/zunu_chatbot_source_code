<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title> @yield('title') | Rent the perfect car</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
    <meta name="keywords" content="Car Sharing" />
    <meta content="Skip the rental car counter and book anything from daily drivers to pickup trucks, from trusted, local hosts on the world’s largest car sharing marketplace." name="description" />
    <meta content="RakeybulHasan" name="author" />
    <meta name="csrf-token" content="{{ csrf_token() }}" />
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --navy:   #0F2D5E;
            --teal:   #0D9488;
            --teal-lt:#CCFBF1;
            --gold:   #F59E0B;
            --gold-lt:#FEF3C7;
            --slate:  #475569;
            --mist:   #F0F4F8;
            --white:  #FFFFFF;
            --border: #E2E8F0;
            --text:   #1E293B;
            --radius: 16px;
        }

        body {
            font-family: 'DM Sans', sans-serif;
            background: var(--white);
            color: var(--text);
            line-height: 1.6;
        }

        /* ── NAV ─────────────────────────────────────── */
        nav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 40px;
            height: 68px;
            background: var(--white);
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
        }
        .logo {
            display: flex; align-items: center; gap: 10px;
            font-family: 'DM Serif Display', serif;
            font-size: 1.5rem; color: var(--navy);
            text-decoration: none;
        }
        .logo-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, var(--navy) 0%, var(--teal) 100%);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem;
        }
        .nav-links { display: flex; gap: 28px; }
        .nav-links a {
            font-size: .9rem; font-weight: 500; color: var(--slate);
            text-decoration: none; transition: color .2s;
        }
        .nav-links a:hover { color: var(--navy); }
        .nav-btn {
            background: var(--navy); color: var(--white);
            padding: 9px 22px; border-radius: 99px;
            font-weight: 600; font-size: .88rem; border: none; cursor: pointer;
            transition: background .2s;
        }
        .nav-btn:hover { background: var(--teal); }

        /* ── HERO ────────────────────────────────────── */
        .hero {
            background: linear-gradient(135deg, var(--navy) 0%, #1E4A8A 55%, var(--teal) 100%);
            padding: 72px 40px 80px;
            text-align: center;
            position: relative; overflow: hidden;
        }
        .hero::before {
            content: '';
            position: absolute; inset: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Ccircle cx='30' cy='30' r='28'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: .5;
        }
        .hero-eyebrow {
            display: inline-block;
            background: rgba(255,255,255,.15);
            color: #A5F3FC; font-size: .8rem; font-weight: 600;
            letter-spacing: .08em; text-transform: uppercase;
            padding: 5px 16px; border-radius: 99px;
            margin-bottom: 20px; position: relative;
        }
        .hero h1 {
            font-family: 'DM Serif Display', serif;
            font-size: clamp(2rem, 5vw, 3.2rem);
            color: var(--white); margin-bottom: 14px;
            position: relative;
        }
        .hero p {
            color: rgba(255,255,255,.75); font-size: 1.05rem;
            max-width: 500px; margin: 0 auto 36px; position: relative;
        }
        .search-bar {
            display: flex; max-width: 580px; margin: 0 auto;
            background: var(--white); border-radius: 99px;
            box-shadow: 0 8px 32px rgba(0,0,0,.25);
            overflow: hidden; position: relative;
        }
        .search-bar input {
            flex: 1; border: none; outline: none;
            padding: 16px 24px; font-size: 1rem;
            font-family: 'DM Sans', sans-serif; color: var(--text);
        }
        .search-bar button {
            background: var(--teal); color: var(--white);
            border: none; padding: 14px 28px;
            font-weight: 600; font-size: .95rem; cursor: pointer;
            font-family: 'DM Sans', sans-serif;
            transition: background .2s; border-radius: 0 99px 99px 0;
        }
        .search-bar button:hover { background: #0B7A71; }
        .hero-pills {
            display: flex; flex-wrap: wrap; gap: 10px;
            justify-content: center; margin-top: 22px; position: relative;
        }
        .hero-pills span {
            background: rgba(255,255,255,.15);
            color: rgba(255,255,255,.9);
            padding: 6px 16px; border-radius: 99px; font-size: .82rem;
            cursor: pointer; border: 1px solid rgba(255,255,255,.2);
            transition: background .2s;
        }
        .hero-pills span:hover { background: rgba(255,255,255,.28); }

        /* ── MAIN LAYOUT ─────────────────────────────── */
        main { max-width: 1160px; margin: 0 auto; padding: 60px 24px 80px; }

        /* ── TABS ────────────────────────────────────── */
        .tabs {
            display: flex; gap: 8px;
            background: var(--mist); border-radius: 99px;
            padding: 6px; width: fit-content; margin: 0 auto 52px;
        }
        .tab {
            padding: 10px 28px; border-radius: 99px;
            border: none; cursor: pointer; font-weight: 600; font-size: .9rem;
            font-family: 'DM Sans', sans-serif; transition: all .2s;
            background: transparent; color: var(--slate);
        }
        .tab.active {
            background: var(--white); color: var(--navy);
            box-shadow: 0 2px 8px rgba(0,0,0,.1);
        }

        /* ── SECTION TITLES ──────────────────────────── */
        .section-label {
            font-size: .72rem; font-weight: 700;
            letter-spacing: .12em; text-transform: uppercase;
            color: var(--teal); margin-bottom: 10px;
        }
        .section-title {
            font-family: 'DM Serif Display', serif;
            font-size: 1.7rem; color: var(--navy); margin-bottom: 32px;
        }

        /* ── CARD GRID ───────────────────────────────── */
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 20px; margin-bottom: 60px;
        }
        .card {
            background: var(--white);
            border: 1.5px solid var(--border);
            border-radius: var(--radius);
            padding: 28px 24px;
            cursor: pointer;
            transition: transform .2s, box-shadow .2s, border-color .2s;
            text-decoration: none; color: inherit;
            display: block;
        }
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 36px rgba(15,45,94,.1);
            border-color: var(--teal);
        }
        .card-icon {
            width: 50px; height: 50px; border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem; margin-bottom: 16px;
        }
        .icon-blue  { background: #EFF6FF; }
        .icon-teal  { background: var(--teal-lt); }
        .icon-gold  { background: var(--gold-lt); }
        .icon-rose  { background: #FFF1F2; }
        .icon-purple{ background: #F5F3FF; }
        .icon-green { background: #F0FDF4; }

        .card h3 {
            font-size: 1rem; font-weight: 700; color: var(--navy);
            margin-bottom: 8px;
        }
        .card p {
            font-size: .875rem; color: var(--slate); line-height: 1.5;
        }
        .card-arrow {
            display: flex; align-items: center; gap: 6px;
            margin-top: 16px; font-size: .82rem; font-weight: 600;
            color: var(--teal);
        }

        /* ── POPULAR ARTICLES ────────────────────────── */
        .articles-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 14px; margin-bottom: 60px;
        }
        .article-item {
            display: flex; align-items: center; gap: 14px;
            padding: 16px 20px; border-radius: 12px;
            border: 1.5px solid var(--border);
            cursor: pointer; transition: all .2s;
            text-decoration: none; color: inherit;
        }
        .article-item:hover {
            border-color: var(--teal);
            background: #F0FDFA;
            transform: translateX(4px);
        }
        .article-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--teal); flex-shrink: 0;
        }
        .article-text { flex: 1; }
        .article-text strong {
            font-size: .9rem; font-weight: 600; color: var(--navy);
            display: block; margin-bottom: 2px;
        }
        .article-text span { font-size: .8rem; color: var(--slate); }
        .article-tag {
            font-size: .72rem; font-weight: 700;
            padding: 4px 10px; border-radius: 99px;
            text-transform: uppercase; letter-spacing: .06em;
        }
        .tag-guest { background: #EFF6FF; color: #1D4ED8; }
        .tag-host  { background: var(--teal-lt); color: #0F766E; }

        /* ── CONTACT STRIP ───────────────────────────── */
        .contact-strip {
            background: linear-gradient(135deg, #F0F4F8 0%, #E0F2FE 100%);
            border-radius: var(--radius); padding: 48px 40px;
            display: flex; align-items: center; justify-content: space-between;
            gap: 32px; flex-wrap: wrap;
        }
        .contact-strip h2 {
            font-family: 'DM Serif Display', serif;
            font-size: 1.6rem; color: var(--navy); margin-bottom: 8px;
        }
        .contact-strip p { color: var(--slate); max-width: 460px; }
        .contact-buttons { display: flex; gap: 12px; flex-wrap: wrap; }
        .contact-btn {
            display: flex; align-items: center; gap: 8px;
            padding: 13px 22px; border-radius: 99px;
            font-weight: 600; font-size: .9rem; cursor: pointer;
            border: 2px solid transparent; transition: all .2s;
            font-family: 'DM Sans', sans-serif;
        }
        .contact-btn.primary {
            background: var(--navy); color: var(--white);
        }
        .contact-btn.primary:hover { background: var(--teal); }
        .contact-btn.secondary {
            background: var(--white); color: var(--navy);
            border-color: var(--navy);
        }
        .contact-btn.secondary:hover {
            background: var(--navy); color: var(--white);
        }

        /* ── STATUS BANNER ───────────────────────────── */
        .status-banner {
            display: flex; align-items: center; gap: 10px;
            background: #F0FDF4; border: 1.5px solid #BBF7D0;
            border-radius: 12px; padding: 14px 20px; margin-bottom: 48px;
            font-size: .88rem; color: #15803D;
        }
        .status-dot {
            width: 10px; height: 10px; border-radius: 50%;
            background: #22C55E; flex-shrink: 0;
            box-shadow: 0 0 0 3px rgba(34,197,94,.2);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 3px rgba(34,197,94,.2); }
            50% { box-shadow: 0 0 0 6px rgba(34,197,94,.1); }
        }

        /* ── FOOTER ──────────────────────────────────── */
        footer {
            background: var(--navy); color: rgba(255,255,255,.65);
            padding: 48px 40px 32px;
        }
        .footer-grid {
            max-width: 1160px; margin: 0 auto;
            display: grid; grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 40px; margin-bottom: 40px;
        }
        .footer-brand .logo { color: var(--white); margin-bottom: 12px; }
        .footer-brand p { font-size: .875rem; line-height: 1.6; }
        .footer-col h4 {
            color: var(--white); font-weight: 700; font-size: .9rem;
            margin-bottom: 16px;
        }
        .footer-col a {
            display: block; color: rgba(255,255,255,.6);
            text-decoration: none; font-size: .875rem; margin-bottom: 10px;
            transition: color .2s;
        }
        .footer-col a:hover { color: var(--white); }
        .footer-bottom {
            max-width: 1160px; margin: 0 auto;
            border-top: 1px solid rgba(255,255,255,.1);
            padding-top: 24px;
            display: flex; justify-content: space-between; align-items: center;
            font-size: .82rem; flex-wrap: wrap; gap: 12px;
        }

        /* ── HOST TAB CONTENT (hidden by default) ────── */
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* ── RESPONSIVE ──────────────────────────────── */
        @media (max-width: 768px) {
            nav { padding: 0 20px; }
            .nav-links { display: none; }
            .hero { padding: 52px 20px 60px; }
            main { padding: 40px 16px 60px; }
            .footer-grid { grid-template-columns: 1fr 1fr; }
            .contact-strip { padding: 32px 24px; }
        }

        /* ── ANIMATIONS ──────────────────────────────── */
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .card { animation: fadeUp .4s ease both; }
        .card:nth-child(1) { animation-delay: .05s; }
        .card:nth-child(2) { animation-delay: .10s; }
        .card:nth-child(3) { animation-delay: .15s; }
        .card:nth-child(4) { animation-delay: .20s; }
        .card:nth-child(5) { animation-delay: .25s; }
        .card:nth-child(6) { animation-delay: .30s; }
        .card:nth-child(7) { animation-delay: .35s; }
        .card:nth-child(8) { animation-delay: .40s; }
    </style>
    @yield('style')
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-E19NHKPM7B"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());

        gtag('config', 'G-E19NHKPM7B');
    </script>
    <!--
    <link rel="stylesheet" href="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/themes/df-messenger-default.css">
    <script src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"></script>
    <df-messenger
        location="us-central1"
        project-id="realdealride"
        agent-id="88b54860-7fe7-437f-9315-dfbcb4df4b75"
        intent="WELCOME"
        storage-option="none"
        language-code="en"
        max-query-length="-1">
        <df-messenger-chat-bubble
            chat-title="Real Deal Ride"
            chat-subtitle="Hi, I'm Zunu! I'm a chatbot here to help you search smarter."
            chat-title-icon="https://realdealride.com/frontend/images/logo/LOGO-2-EPS-BLACK-1.png"
            bot-writing-text="Typing..."
            placeholder-text="Ask about cars, prices, locations..."
            chat-icon="https://realdealride.com/frontend/images/logo/LOGO-2-EPS-BLACK-1.png"
            bot-actor-image="https://realdealride.com/frontend/images/logo/LOGO-2-EPS-BLACK-1.png"
            user-actor-image="https://img.icons8.com/?size=100&id=_CRnLLWFDr9I&format=png&color=000000"
        >
        </df-messenger-chat-bubble>
    </df-messenger>
    -->
    
    <!-- RealDealRide AI Chatbot Widget -->
    @if(Auth::check())
        <script src="{{ asset('js/rdr_chatbot.js') }}" 
                data-member-id="{{ Auth::id() }}" 
                data-jwt-token="{{ App\Helpers\ChatbotHelper::generateToken(Auth::id()) }}" 
                defer></script>
    @else
        <script src="{{ asset('js/rdr_chatbot.js') }}" defer></script>
    @endif
    @yield('header.styles')
    <style>
        /*
        df-messenger {
            z-index: 999;
            position: fixed;
            --df-messenger-font-color: #000;
            --df-messenger-font-family: Google Sans;
            --df-messenger-chat-background: #f3f6fc;
            --df-messenger-message-user-background: #d3e3fd;
            --df-messenger-message-bot-background: #fff;
            bottom: 16px;
            right: 16px;
        }
        */
        #titlebar-title h2, #titlebar-title h3{
            white-space: initial !important;
        }
        .menu-logo img {
             height: 50px;
        }

        @media (max-width: 991px) {
            .menu-logo img {
                height: 24px;
            }
        }

        .avatar {
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            text-transform: uppercase;
            color: #fff;
        }

        .avatar-sm { width: 40px; height: 40px; font-size: 16px; }
        .avatar-md { width: 60px; height: 60px; font-size: 20px; }
        .avatar-lg { width: 80px; height: 80px; font-size: 26px; }

        .bg-blue { background: #0d6efd; }
        .bg-green { background: #198754; }
        .bg-red { background: #dc3545; }


        /* Container */
        .profile-dropdown {
            position: relative;
            display: inline-block;
        }

        /* Hide checkbox */
        #dropdown-toggle {
            display: none;
        }

        /* Profile Button */
        .profile-btn {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            background: #fff;
            padding: 6px 10px;
            border-radius: 6px;
        }

        .profile-btn img {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            object-fit: cover;
        }

        .profile-btn span {
            font-size: 14px;
            font-weight: 500;
        }

        .profile-btn .arrow {
            font-size: 10px;
            margin-left: 4px;
        }

        /* Dropdown Menu */
        .dropdown-menu {
            position: absolute;
            top: 110%;
            right: 0;
            width: 220px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.08);
            padding: 8px 0;
            opacity: 0;
            visibility: hidden;
            transform: translateY(10px);
            transition: 0.25s ease;
        }

        /* Show when checked */
        #dropdown-toggle:checked + .profile-btn + .dropdown-menu {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }

        /* List */
        .dropdown-menu ul {
            list-style: none;
            margin: 0;
            padding: 0;
        }

        .dropdown-menu li {
            width: 100%;
        }

        .dropdown-menu a {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 16px;
            text-decoration: none;
            color: #333;
            font-size: 14px;
            transition: 0.2s;
        }

        .dropdown-menu a:hover {
            background: #f2f2f2;
        }

        /* Divider */
        .divider {
            height: 1px;
            background: #eee;
            margin: 6px 0;
        }

        /* Logout Style */
        .logout {
            color: #dc3545;
        }

        .logout:hover {
            background: #fdeaea;
        }

        /* Small icons */
        .icon {
            font-size: 14px;
        }
    </style>
</head>

<body>

<!--====== header -->

    @include('layouts.help-include.header')

<!--=============== header -->

    @yield('content')

    <!-- Footer -->
    @include('layouts.help-include.footer')
    <!-- /Footer -->

    <!-- JAVASCRIPT -->
{{--    @include('layouts.vendor-scripts')--}}

   @stack('scripts')

   @yield('footer.scripts')

   <script>
    if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/firebase-messaging-sw.js')
        .then(function(registration) {
            console.log('Service Worker registered with scope:', registration.scope);
        })
        .catch(function(error) {
            console.log('Service Worker registration failed:', error);
        });
}
   </script>
<script>
    function switchTab(tab, el) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
        document.getElementById(tab + '-content').classList.add('active');
    }

    // Search pill click
    document.querySelectorAll('.hero-pills span').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelector('.search-bar input').value = pill.textContent;
        });
    });
</script>
</body>

</html>
