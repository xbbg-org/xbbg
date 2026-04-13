// @ts-check
import { defineConfig, passthroughImageService } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';
import { createStarlightTypeDocPlugin } from 'starlight-typedoc';

const [coreTypeDoc, coreTypeDocSidebarGroup] = createStarlightTypeDocPlugin();

// https://astro.build/config
export default defineConfig({
	site: 'https://alpha-xone.github.io',
	base: '/xbbg',
	image: {
		service: passthroughImageService(),
	},
	integrations: [
		starlight({
			title: 'xbbg',
			description: 'Public documentation for the xbbg Python package and @xbbg/core Node.js package',
			logo: {
				src: './src/assets/xbbg-logo.png',
				alt: 'xbbg logo',
			},
			disable404Route: true,
			plugins: [
				starlightLlmsTxt(),
				coreTypeDoc({
					entryPoints: ['../js-xbbg/index.d.ts'],
					output: 'javascript/api/core',
					sidebar: { label: '@xbbg/core API', collapsed: true },
					tsconfig: './typedoc/js-core.json',
					typeDoc: { name: '@xbbg/core' },
				}),
			],
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/alpha-xone/xbbg' },
			],
			sidebar: [
				{
					label: 'Overview',
					items: [{ label: 'Package Map', slug: 'overview/package-map' }],
				},
				{
					label: 'Python',
					items: [
						{ label: 'Overview', slug: 'python' },
						{ label: 'Installation', slug: 'python/installation' },
						{ label: 'Quick Start', slug: 'python/quickstart' },
						{
							label: 'Guides',
							items: [
								{ label: 'DataFrame Backends', slug: 'python/guides/backends' },
								{ label: 'Output Formats', slug: 'python/guides/output-formats' },
								{ label: 'Async Patterns', slug: 'python/guides/async' },
								{ label: 'Streaming Data', slug: 'python/guides/streaming' },
								{ label: 'Migration from Legacy', slug: 'python/guides/migration' },
							],
						},
						{ label: 'API Reference', autogenerate: { directory: 'python/api' } },
						{
							label: 'Reference',
							items: [
								{ label: 'Configuration', slug: 'python/reference/configuration' },
								{ label: 'Type Mappings', slug: 'python/reference/type-mappings' },
							],
						},
					],
				},
				{
					label: 'JavaScript',
					items: [
						{ label: 'Overview', slug: 'javascript' },
						{ label: 'Installation', slug: 'javascript/installation' },
						coreTypeDocSidebarGroup,
					],
				},
				{
					label: 'Release Notes',
					items: [{ label: 'Changelog', slug: 'releases/changelog' }],
				},
			],
			editLink: {
				baseUrl: 'https://github.com/alpha-xone/xbbg/edit/main/docs/',
			},
		}),
	],
});