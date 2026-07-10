/**
 * Tailwind CSS build config for the Pharmacy Debt System.
 *
 * The app used to rely on the browser build (cdn.tailwindcss.com, which serves
 * Tailwind v3.4.x). To work fully offline we now compile the same utilities to a
 * static file: static/css/tailwind.css. See "Rebuilding Tailwind" in README.md.
 *
 * Only the utility classes actually found in the scanned files are emitted, so
 * the output stays small. `hidden`/`flex` are safelisted because they are toggled
 * at runtime by the mobile/desktop menu JS.
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/**/*.js',
  ],
  safelist: [
    'hidden',
    'flex',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
