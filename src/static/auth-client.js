(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  var token = meta ? meta.getAttribute("content") : "";
  var nativeFetch = window.fetch.bind(window);
  var unsafe = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  window.fetch = function (input, options) {
    var request = input instanceof Request ? input : null;
    var url = new URL(request ? request.url : input, window.location.href);
    var init = Object.assign({}, options || {});
    var method = String(init.method || (request && request.method) || "GET").toUpperCase();

    if (url.origin === window.location.origin && unsafe.has(method)) {
      var headers = new Headers(init.headers || (request && request.headers) || {});
      if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", token);
      init.headers = headers;
      init.credentials = "same-origin";
    }

    return nativeFetch(input, init).then(function (response) {
      if (response.status === 401 && url.origin === window.location.origin) {
        window.location.assign("/login?next=" + encodeURIComponent(window.location.pathname + window.location.search));
      }
      return response;
    });
  };
})();
