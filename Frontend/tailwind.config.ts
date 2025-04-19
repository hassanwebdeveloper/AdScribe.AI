import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";
import typography from "@tailwindcss/typography";

export default {
	darkMode: ["class"],
	content: [
		"./pages/**/*.{ts,tsx}",
		"./components/**/*.{ts,tsx}",
		"./app/**/*.{ts,tsx}",
		"./src/**/*.{ts,tsx}",
	],
	prefix: "",
	theme: {
		container: {
			center: true,
			padding: '2rem',
			screens: {
				'2xl': '1400px'
			}
		},
		extend: {
			colors: {
				border: 'hsl(var(--border))',
				input: 'hsl(var(--input))',
				ring: 'hsl(var(--ring))',
				background: 'hsl(var(--background))',
				foreground: 'hsl(var(--foreground))',
				primary: {
					DEFAULT: 'hsl(var(--primary))',
					foreground: 'hsl(var(--primary-foreground))'
				},
				secondary: {
					DEFAULT: 'hsl(var(--secondary))',
					foreground: 'hsl(var(--secondary-foreground))'
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive))',
					foreground: 'hsl(var(--destructive-foreground))'
				},
				muted: {
					DEFAULT: 'hsl(var(--muted))',
					foreground: 'hsl(var(--muted-foreground))'
				},
				accent: {
					DEFAULT: 'hsl(var(--accent))',
					foreground: 'hsl(var(--accent-foreground))'
				},
				popover: {
					DEFAULT: 'hsl(var(--popover))',
					foreground: 'hsl(var(--popover-foreground))'
				},
				card: {
					DEFAULT: 'hsl(var(--card))',
					foreground: 'hsl(var(--card-foreground))'
				},
				sidebar: {
					DEFAULT: 'hsl(var(--sidebar-background))',
					foreground: 'hsl(var(--sidebar-foreground))',
					primary: 'hsl(var(--sidebar-primary))',
					'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
					accent: 'hsl(var(--sidebar-accent))',
					'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
					border: 'hsl(var(--sidebar-border))',
					ring: 'hsl(var(--sidebar-ring))'
				},
				brand: {
					'50': '#f5f3ff',
					'100': '#ede9fe',
					'200': '#ddd6fe',
					'300': '#c4b5fd',
					'400': '#a78bfa',
					'500': '#8b5cf6',
					'600': '#7c3aed',
					'700': '#6d28d9',
					'800': '#5b21b6',
					'900': '#4c1d95',
				},
				chat: {
					'user': '#f9fafb',
					'bot': '#8b5cf6',
					'bot-light': '#ede9fe',
					'user-border': '#e5e7eb',
					'bot-border': '#a78bfa',
				}
			},
			borderRadius: {
				lg: 'var(--radius)',
				md: 'calc(var(--radius) - 2px)',
				sm: 'calc(var(--radius) - 4px)'
			},
			keyframes: {
				'accordion-down': {
					from: {
						height: '0'
					},
					to: {
						height: 'var(--radix-accordion-content-height)'
					}
				},
				'accordion-up': {
					from: {
						height: 'var(--radix-accordion-content-height)'
					},
					to: {
						height: '0'
					}
				},
                'typing': {
                    '0%': { width: '0%' },
                    '100%': { width: '100%' }
                },
                'blink': {
                    '50%': { borderColor: 'transparent' }
                },
                'bounce-in': {
                    '0%': { transform: 'scale(0.9)', opacity: '0' },
                    '100%': { transform: 'scale(1)', opacity: '1' }
                },
                'fade-in': {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' }
                }
			},
			animation: {
				'accordion-down': 'accordion-down 0.2s ease-out',
				'accordion-up': 'accordion-up 0.2s ease-out',
                'typing': 'typing 1.5s ease-in-out infinite',
                'cursor-blink': 'blink 0.7s infinite',
                'bounce-in': 'bounce-in 0.3s ease-out',
                'fade-in': 'fade-in 0.3s ease-out'
			},
			typography: {
				DEFAULT: {
					css: {
						maxWidth: 'none',
						color: 'var(--tw-prose-body)',
						'> *': {
							marginTop: '0',
							marginBottom: '0'
						},
						p: {
							marginTop: '0',
							marginBottom: '1em'
						},
						'h1, h2, h3, h4, h5, h6': {
							marginTop: '1.5em',
							marginBottom: '0.5em',
							fontWeight: '700',
							lineHeight: '1.2',
						},
						pre: {
							backgroundColor: '#1f2937',
							color: '#e5e7eb',
							fontSize: '0.875rem',
							lineHeight: '1.7',
							margin: '1rem 0',
							padding: '1rem',
							borderRadius: '0.375rem',
							overflowX: 'auto',
						},
						code: {
							color: '#111827',
							backgroundColor: '#e5e7eb',
							borderRadius: '0.25rem',
							padding: '0.125rem 0.25rem',
							fontWeight: '500',
							'&::before': {
								content: 'none',
							},
							'&::after': {
								content: 'none',
							},
						},
						'pre code': {
							color: '#e5e7eb',
							backgroundColor: 'transparent',
							padding: '0',
						},
					}
				}
			}
		}
	},
	plugins: [
		tailwindcssAnimate,
		typography
	],
} satisfies Config;
