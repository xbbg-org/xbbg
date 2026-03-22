// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';

// https://astro.build/config
export default defineConfig({
	site: 'https://alpha-xone.github.io',
	base: '/xbbg',
	integrations: [
		starlight({
			title: 'xbbg',
			description: 'An intuitive Bloomberg API for Python — powered by Rust',
			logo: {
				src: './src/assets/xbbg-logo.png',
				alt: 'xbbg logo',
			},
			plugins: [starlightLlmsTxt()],
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/alpha-xone/xbbg' },
			],
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Introduction', slug: 'getting-started/introduction' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Quick Start', slug: 'getting-started/quickstart' },
					],
				},
				{
					label: 'API Reference',
					autogenerate: { directory: 'api' },
				},
				{
					label: 'Guides',
					items: [
						{ label: 'DataFrame Backends', slug: 'guides/backends' },
						{ label: 'Output Formats', slug: 'guides/output-formats' },
						{ label: 'Async Patterns', slug: 'guides/async' },
						{ label: 'Streaming Data', slug: 'guides/streaming' },
						{ label: 'Migration from Legacy', slug: 'guides/migration' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Configuration', slug: 'reference/configuration' },
						{ label: 'Type Mappings', slug: 'reference/type-mappings' },
						{ label: 'Changelog', slug: 'reference/changelog' },
					],
				},
			],
			editLink: {
				baseUrl: 'https://github.com/alpha-xone/xbbg/edit/main/docs/',
			},
		}),
	],
});
