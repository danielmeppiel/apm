import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLinksValidator from "starlight-links-validator";
import starlightLlmsTxt from "starlight-llms-txt";

export default defineConfig({
  site: "https://microsoft.github.io",
  base: "/apm",
  integrations: [
    starlight({
      title: "APM",
      description:
        "Agent Package Manager — dependency management for AI coding agents",
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/microsoft/apm",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/microsoft/apm/edit/main/docs/",
      },
      plugins: [starlightLinksValidator(), starlightLlmsTxt()],
      sidebar: [
        {
          label: "Introduction",
          items: [
            { label: "Overview", slug: "introduction/overview" },
            { label: "How It Works", slug: "introduction/how-it-works" },
            { label: "Key Concepts", slug: "introduction/key-concepts" },
          ],
        },
        {
          label: "Getting Started",
          items: [
            { label: "Installation", slug: "getting-started/installation" },
            {
              label: "Your First Package",
              slug: "getting-started/first-package",
            },
          ],
        },
        {
          label: "Guides",
          items: [
            {
              label: "Compilation & Optimization",
              slug: "guides/compilation",
            },
            { label: "Skills & Prompts", slug: "guides/skills-and-prompts" },
            { label: "Plugins", slug: "guides/plugins" },
            {
              label: "Dependencies & Lockfile",
              slug: "guides/dependencies",
            },
            { label: "APM in CI/CD", slug: "guides/cicd" },
          ],
        },
        {
          label: "Integrations",
          items: [
            {
              label: "GitHub Agentic Workflows",
              slug: "integrations/github-agentic-workflows",
            },
            {
              label: "AI Runtime Compatibility",
              slug: "integrations/runtime-compatibility",
            },
            {
              label: "IDE & Tool Integration",
              slug: "integrations/ide-and-tools",
            },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "CLI Commands", slug: "reference/cli" },
            { label: "Manifest Schema", slug: "reference/manifest-schema" },
            { label: "Primitive Types", slug: "reference/primitive-types" },
            { label: "Examples", slug: "reference/examples" },
          ],
        },
        {
          label: "Contributing",
          items: [
            {
              label: "Development Guide",
              slug: "contributing/development-guide",
            },
            { label: "Changelog", slug: "contributing/changelog" },
          ],
        },
      ],
    }),
  ],
});
