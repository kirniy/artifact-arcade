# Software Documentation

This directory contains technical documentation for ARTIFACT's software architecture.

## Contents

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | System architecture, layers, and component overview |
| [animation-system.md](animation-system.md) | Timeline-based animation engine and effects |
| [ai-integration.md](ai-integration.md) | Gemini AI integration for predictions and caricatures |

## Quick Start

### Running the Simulator

```bash
# From project root
cd /Users/kirniy/dev/modular-arcade

# Install dependencies
pip install -e .

# Run simulator
artifact-sim
```

### Key Concepts

1. **State Machine**: Controls application flow (IDLE → MODE_SELECT → MODE_ACTIVE → etc.)
2. **Event Bus**: Pub/sub communication between components
3. **Hardware Abstraction**: Unified interface for real hardware and simulator

### Development Workflow

1. Develop and test in simulator (pygame)
2. Use mock hardware implementations
3. Test on Raspberry Pi with real hardware
4. Factory pattern auto-selects correct implementation

## Architecture Overview

```
Application Layer (Modes)
         │
    Core Layer (State, Events, Scheduler)
         │
   Service Layer (Animation, Graphics, AI, Audio)
         │
Hardware Abstraction Layer (Real ←→ Simulator)
```

See [architecture.md](architecture.md) for detailed documentation.
