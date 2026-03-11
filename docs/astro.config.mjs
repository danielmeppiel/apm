// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';
import starlightLinksValidator from 'starlight-links-validator';
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
	site: 'https://microsoft.github.io',
	base: '/apm/',
	integrations: [
		mermaid(),
		starlight({
			title: 'Agent Package Manager',
			description: 'An open-source, community-driven dependency manager for AI agents. Declare skills, prompts, instructions, and tools in apm.yml — install with one command.',
			favicon: '/favicon.svg',
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/microsoft/apm' },
			],
			tableOfContents: {
				minHeadingLevel: 2,
				maxHeadingLevel: 4,
			},
			pagination: true,
			customCss: ['./src/styles/custom.css'],
			expressiveCode: {
				frames: {
					showCopyToClipboardButton: true,
				},
			},
			plugins: [
				starlightLinksValidator({
					errorOnRelativeLinks: false,
					errorOnLocalLinks: true,
				}),
				starlightLlmsTxt({
					description: 'APM (Agent Package Manager) is an open-source dependency manager for AI agents. It lets you declare skills, prompts, instructions, agents, hooks, plugins, and MCP servers in a single apm.yml manifest, resolving transitive dependencies automatically.',
				}),
			],
			sidebar: [
				{
					label: 'Introduction',
					items: [
						{ label: 'Why APM?', slug: 'introduction/why-apm' },
						{ label: 'How It Works', slug: 'introduction/how-it-works' },
						{ label: 'Key Concepts', slug: 'introduction/key-concepts' },
					],
				},
				{
					label: 'Getting Started',
					items: [
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Your First Package', slug: 'getting-started/first-package' },
						{ label: 'Authentication', slug: 'getting-started/authentication' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Compilation & Optimization', slug: 'guides/compilation' },
						{ label: 'Skills', slug: 'guides/skills' },
						{ label: 'Prompts', slug: 'guides/prompts' },
						{ label: 'Plugins', slug: 'guides/plugins' },
						{ label: 'Dependencies & Lockfile', slug: 'guides/dependencies' },
					],
				},
				{
					label: 'Integrations',
					items: [
						{ label: 'GitHub Agentic Workflows', slug: 'integrations/gh-aw' },
						{ label: 'APM in CI/CD', slug: 'integrations/ci-cd' },
						{ label: 'AI Runtime Compatibility', slug: 'integrations/runtime-compatibility' },
						{ label: 'IDE & Tool Integration', slug: 'integrations/ide-tool-integration' },
					],
				},
				{
					label: 'Reference',
					autogenerate: { directory: 'reference' },
				},
				{
					label: 'Contributing',
					autogenerate: { directory: 'contributing' },
				},
			],
		}),
	],
});
