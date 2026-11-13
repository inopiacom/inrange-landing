// One switch for "is inRange live in the App Store?".
//
// While false, every page shows "Coming soon to the App Store" and no badge:
// Apple's marketing guidelines allow the "Download on the App Store" badge only
// as a link to an app that is actually available. Invite pages keep their
// TestFlight link until then.
//
// When the app is approved and released, flip this to true. That single change
// shows the badge on the home page, hides the notify-me form, and points the
// install steps on the invite pages (join/, l/, friends/accept.html) at the
// App Store instead of TestFlight, with matching copy.
//
// Without JavaScript the pages stay in the "coming soon" state, which is the
// safe direction: it never shows a badge that leads nowhere.
(function () {
  var APP_STORE_LIVE = false;
  var APP_STORE_URL = 'https://apps.apple.com/app/id6788735095';

  var root = document.documentElement;
  root.setAttribute('data-appstore', APP_STORE_LIVE ? 'live' : 'soon');
  window.INRANGE_APPSTORE = { live: APP_STORE_LIVE, url: APP_STORE_URL };

  // Invite pages call this after they have written their own copy. It turns
  // their TestFlight badge into Apple's official App Store badge.
  window.INRANGE_APPSTORE.useStoreBadge = function (anchorId) {
    if (!APP_STORE_LIVE) return;
    var a = document.getElementById(anchorId);
    if (!a) return;
    a.href = APP_STORE_URL;
    a.setAttribute('aria-label', 'Download inRange on the App Store');
    a.innerHTML = '<img src="/assets/badges/download-on-the-app-store-black-en.svg" ' +
      'alt="Download on the App Store" style="height:48px;width:auto" />';
  };
})();
