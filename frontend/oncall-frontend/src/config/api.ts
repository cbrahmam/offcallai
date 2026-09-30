const _apiUrl = process.env.REACT_APP_API_URL;

if (!_apiUrl && process.env.NODE_ENV !== 'development') {
  // A production bundle with no API URL baked in cannot talk to anything, and
  // throwing here would leave an unexplained blank page. Say why on the page
  // itself before failing.
  const message =
    'REACT_APP_API_URL was not set when this bundle was built, so the app has ' +
    'no API to talk to. Set it (see .env.example) and rebuild, or pass it to ' +
    'the Docker build: --build-arg REACT_APP_API_URL=https://your-host/api/v1';

  const render = () => {
    document.body.innerHTML =
      '<div style="font:14px/1.6 system-ui,sans-serif;max-width:40rem;margin:4rem auto;' +
      'padding:1.5rem;border:1px solid #d33;border-radius:8px;color:#eee;background:#1a1a1a">' +
      '<strong style="color:#f66">Configuration error</strong><p>' + message + '</p></div>';
  };
  if (document.body) {
    render();
  } else {
    document.addEventListener('DOMContentLoaded', render);
  }

  throw new Error(`FATAL: ${message}`);
}

export const API_URL: string = _apiUrl || 'http://localhost:8000/api/v1';
