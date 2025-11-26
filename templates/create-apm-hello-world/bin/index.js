#!/usr/bin/env node

/**
 * create-apm-hello-world
 * 
 * APM template for getting started with AI-Native Development.
 * This template creates a minimal APM project with example prompts
 * and instructions to help you get started quickly.
 * 
 * Usage:
 *   npx create-apm-hello-world my-project
 *   apm init hello-world my-project
 */

const fs = require('fs');
const path = require('path');

// Parse command line arguments
const args = process.argv.slice(2);
const projectName = args[0] || 'my-apm-project';
const targetDir = path.resolve(process.cwd(), projectName);

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  cyan: '\x1b[36m',
  yellow: '\x1b[33m',
};

console.log(`\n${colors.cyan}${colors.bright}Creating APM project: ${projectName}${colors.reset}\n`);

// Check if directory already exists
if (fs.existsSync(targetDir)) {
  const files = fs.readdirSync(targetDir);
  if (files.length > 0) {
    console.error(`${colors.yellow}Warning: Directory "${projectName}" is not empty${colors.reset}`);
    console.error('Please choose an empty directory or a new project name.\n');
    process.exit(1);
  }
}

// Create project directory
fs.mkdirSync(targetDir, { recursive: true });

// Copy template files
const templatesDir = path.join(__dirname, '..', 'templates');
copyDir(templatesDir, targetDir);

// Get author from git config (best effort)
let author = 'Developer';
try {
  const { execSync } = require('child_process');
  author = execSync('git config user.name', { encoding: 'utf8' }).trim() || author;
} catch (e) {
  // Git not available or not configured, use default
}

// Substitute variables in apm.yml
const apmYmlPath = path.join(targetDir, 'apm.yml');
let apmYml = fs.readFileSync(apmYmlPath, 'utf8');
apmYml = apmYml
  .replace(/{{project_name}}/g, projectName)
  .replace(/{{author}}/g, author)
  .replace(/{{year}}/g, new Date().getFullYear().toString());
fs.writeFileSync(apmYmlPath, apmYml);

// Substitute variables in README.md
const readmePath = path.join(targetDir, 'README.md');
let readme = fs.readFileSync(readmePath, 'utf8');
readme = readme
  .replace(/{{project_name}}/g, projectName)
  .replace(/{{author}}/g, author)
  .replace(/{{year}}/g, new Date().getFullYear().toString());
fs.writeFileSync(readmePath, readme);

// Print success message
console.log(`${colors.green}✨ Successfully created APM project!${colors.reset}\n`);

console.log(`${colors.bright}Next steps:${colors.reset}`);
console.log(`  ${colors.cyan}cd ${projectName}${colors.reset}`);
console.log(`  ${colors.cyan}apm runtime setup copilot${colors.reset}   # Install coding agent`);
console.log(`  ${colors.cyan}apm compile${colors.reset}                 # Generate AGENTS.md`);
console.log(`  ${colors.cyan}apm run start${colors.reset}               # Run hello world prompt`);
console.log();

console.log(`${colors.bright}Project structure:${colors.reset}`);
console.log(`  ${projectName}/`);
console.log(`  ├── apm.yml                         # Project configuration`);
console.log(`  ├── hello-world.prompt.md           # Example prompt`);
console.log(`  ├── README.md                       # Project documentation`);
console.log(`  └── .apm/`);
console.log(`      ├── instructions/               # AI instructions`);
console.log(`      └── chatmodes/                  # AI personas`);
console.log();

console.log(`${colors.bright}Learn more:${colors.reset}`);
console.log(`  https://github.com/danielmeppiel/apm`);
console.log();

/**
 * Recursively copy a directory
 */
function copyDir(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    
    if (entry.isDirectory()) {
      fs.mkdirSync(destPath, { recursive: true });
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}
