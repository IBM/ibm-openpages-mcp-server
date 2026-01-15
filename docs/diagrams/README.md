# OpenPages MCP Server - Architecture Diagrams

This directory contains architecture diagrams for the OpenPages MCP Server in various formats.

## Available Diagrams

### 1. Remote Mode Architecture
- **File**: `remote-mode-architecture.mmd`
- **Format**: Mermaid
- **Description**: Complete architecture for remote (HTTP) deployment mode showing all layers from clients to OpenPages backend

### 2. Local Mode Architecture
- **File**: `local-mode-architecture.mmd`
- **Format**: Mermaid
- **Description**: Complete architecture for local (stdio) deployment mode showing process-based communication

### 3. Deployment Comparison
- **File**: `deployment-comparison.mmd`
- **Format**: Mermaid
- **Description**: Side-by-side comparison of remote and local deployment modes

## How to View the Diagrams

### Option 1: GitHub (Recommended)
GitHub automatically renders Mermaid diagrams. Simply view the `.mmd` files directly on GitHub.

### Option 2: VS Code
1. Install the "Markdown Preview Mermaid Support" extension
2. Open any `.mmd` file
3. Use the preview pane to view the rendered diagram

### Option 3: Online Mermaid Editor
1. Go to https://mermaid.live/
2. Copy the content of any `.mmd` file
3. Paste into the editor
4. View and export the diagram

### Option 4: Command Line (Generate PNG/SVG)
Install Mermaid CLI:
```bash
npm install -g @mermaid-js/mermaid-cli
```

Generate images:
```bash
# Generate PNG
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.png

# Generate SVG
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.svg

# Generate PDF
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.pdf
```

### Option 5: Markdown Preview
Create a markdown file with the diagram:
```markdown
# Architecture Diagram

```mermaid
[paste diagram content here]
```
```

Then preview the markdown file in VS Code or GitHub.

## Diagram Legend

### Colors
- **Light Blue** (#e1f5ff): Client applications
- **Light Orange** (#fff4e6): Network/proxy layer
- **Light Green** (#e8f5e9): Application/server layer
- **Light Yellow** (#fff9c4): Transport/communication layer
- **Light Purple** (#f3e5f5): Backend/OpenPages layer
- **Light Pink** (#fce4ec): Monitoring/observability layer

### Arrows
- **Solid arrows** (→): Direct communication flow
- **Dashed arrows** (⇢): Response/callback flow
- **Labels**: Protocol or communication method

## Detailed Documentation

For comprehensive deployment architecture documentation, see:
- [DEPLOYMENT_ARCHITECTURE.md](../DEPLOYMENT_ARCHITECTURE.md)

This document includes:
- Detailed component descriptions
- Deployment options and steps
- Security considerations
- Monitoring setup
- Troubleshooting guides
- Comparison tables

## Exporting Diagrams

### To PNG (High Resolution)
```bash
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.png -w 2400 -H 1800
```

### To SVG (Vector, Scalable)
```bash
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.svg
```

### To PDF (Print-Ready)
```bash
mmdc -i remote-mode-architecture.mmd -o remote-mode-architecture.pdf
```

### Batch Export All Diagrams
```bash
# Create a script to export all diagrams
for file in *.mmd; do
    base="${file%.mmd}"
    mmdc -i "$file" -o "${base}.png" -w 2400 -H 1800
    mmdc -i "$file" -o "${base}.svg"
done
```

## Customizing Diagrams

The Mermaid diagrams can be customized by:

1. **Changing colors**: Modify the `style` statements at the end of each diagram
2. **Adding nodes**: Add new components with unique IDs
3. **Modifying connections**: Change arrow types and labels
4. **Adjusting layout**: Use subgraphs to organize components

Example customization:
```mermaid
style NodeID fill:#color,stroke:#color,stroke-width:2px
```

## Integration with Documentation

These diagrams are referenced in:
- Main README.md
- DEPLOYMENT_ARCHITECTURE.md
- Setup and deployment guides

## Contributing

When adding new diagrams:
1. Use the `.mmd` extension for Mermaid files
2. Follow the existing naming convention
3. Add appropriate colors and styling
4. Update this README with the new diagram
5. Test rendering in multiple viewers

## Resources

- [Mermaid Documentation](https://mermaid.js.org/)
- [Mermaid Live Editor](https://mermaid.live/)
- [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli)
- [GitHub Mermaid Support](https://github.blog/2022-02-14-include-diagrams-markdown-files-mermaid/)