(function () {
    const cleanupUrl = '/cleanup/';
    const cancelUrl = '/cleanup/cancel/';

    // On every page load, tell the server "I'm still here" — this cancels
    // any pending deletion left over from a refresh's pagehide event.
    fetch(cancelUrl, { method: 'POST', keepalive: true }).catch(() => {});

    // On unload (refresh OR close — indistinguishable at this point),
    // mark the user for deletion. If this was a refresh, the next page
    // load's cancelUrl call above will undo it in time.
    window.addEventListener('pagehide', function () {
        navigator.sendBeacon(cleanupUrl);
    });
})();