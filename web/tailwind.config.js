/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        sakura: {
          50: "#fff1f6",
          100: "#ffd9e8",
          200: "#ffb7d2",
          300: "#ff94bc",
          400: "#ff6ea5",
          500: "#f94f8e",
          600: "#df2f72",
          700: "#b8225a",
          800: "#921b47",
          900: "#701838"
        },
        mint: {
          100: "#d8fff5",
          300: "#86efd8",
          500: "#37d5b4",
          700: "#1e987f"
        }
      },
      boxShadow: {
        glow: "0 10px 40px rgba(255, 110, 165, 0.35)"
      }
    }
  },
  plugins: []
};
