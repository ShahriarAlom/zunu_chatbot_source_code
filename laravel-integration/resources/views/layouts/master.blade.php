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
    <!-- App favicon -->
    <link rel="shortcut icon" href="{{ URL::asset('frontend/images/favicon.ico') }}">
    @include('layouts.head-css')
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
    </style>
</head>

<body>

<div id="loading">
    <div id="loading-center">
        <img src="{{asset('frontend/images/loader3.gif')}}" alt="">
    </div>
</div>

<!--====== header -->

    @include('layouts.header')

<!--=============== header -->

    @yield('content')

    <!-- Footer -->
    @include('layouts.footer')
    <!-- /Footer -->

    <!-- JAVASCRIPT -->
    @include('layouts.vendor-scripts')

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


    <!-- Firebase script temporarily disabled to prevent syntax errors -->
    <!--
    <script type="module">
        try {
            const { initializeApp } = await import("https://www.gstatic.com/firebasejs/10.0.0/firebase-app.js");
            const { getMessaging, getToken, onMessage } = await import("https://www.gstatic.com/firebasejs/10.0.0/firebase-messaging.js");

            // Your Firebase configuration
            const firebaseConfig = {
                apiKey: "AIzaSyC1a3SoUMUcbTpemlkcJZClA-wjBzrvn0U",
                authDomain: "real-deal-ride-749f3.firebaseapp.com",
                projectId: "real-deal-ride-749f3",
                storageBucket: "real-deal-ride-749f3.firebasestorage.app",
                messagingSenderId: "1040856340118",
                appId: "1:1040856340118:web:a0e67680656a1cd81554b7",
                measurementId: "G-ETB60EXN40"
            };

            // Initialize Firebase
            const app = initializeApp(firebaseConfig);
            const messaging = getMessaging(app);

            // Request permission for notifications
            Notification.requestPermission()
                .then((permission) => {
                    console.log("Notification Permission:", permission);
                    if (permission === "granted") {
                        return getToken(messaging, { vapidKey: "BA13F3SnknOUdOTzFoFU2DLnr4xz894Rn0iG8pvFIlvucxvGuvNeY_6FMC6HhLYB_INs39kN1d4Eta4Xo2Iwr2A" });
                    } else {
                        throw new Error("Permission denied");
                    }
                })
                .then((token) => {
                    console.log("FCM Token:", token);

                    // Send token to server
                    fetch('/save-token', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]').content
                        },
                        body: JSON.stringify({ token }),
                    });
                })
                .catch((error) => {
                    console.error("Error getting FCM token:", error);
                });

            // Handle incoming foreground messages
            onMessage(messaging, (payload) => {
                console.log("Foreground message received:", payload);

                if (payload.notification) {
                    const notification = payload.notification;
                    new Notification(notification.title, {
                        body: notification.body,
                        icon: notification.icon,
                    });
                }
            });
        } catch (error) {
            console.log('Firebase initialization failed:', error);
        }
    </script>
    -->
</body>

</html>
