/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Warm/Earthy palette based on reference image
                primary: {
                    50: '#fdf8f6',
                    100: '#f2e8e5',
                    200: '#eaddd7',
                    300: '#e0cec7',
                    400: '#d2bab0',
                    500: '#a08072', // Muted brown/terracotta
                    600: '#8a6a5c',
                    700: '#745446',
                    800: '#5e4034',
                    900: '#483026',
                },
                background: {
                    light: '#FDF6F0', // Main background beige
                    paper: '#FFFFFF',
                    sidebar: '#E6D5CC', // Darker beige for sidebar? Or maybe just use light.
                },
                accent: {
                    DEFAULT: '#C8A288', // Button color
                    hover: '#B08B72',
                }
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'], // Keep clean sans-serif
            }
        },
    },
    plugins: [],
}
