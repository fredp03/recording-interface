# Recording Interface

A React-based recording interface with interactive faders and controls.

## Getting started

> **Prerequisites:**
> The following steps require [NodeJS](https://nodejs.org/en/) to be installed on your system, so please
> install it beforehand if you haven't already.

To get started with your project, you'll first need to install the dependencies with:

```
npm install
```

Then, you'll be able to run a development version of the project with:

```
npm run dev
```

## Features

- Interactive draggable faders with visual feedback
- Recording controls (play, record, undo, redo)
- Section buttons for navigation
- Responsive design optimized for mobile interfaces

## Development

The project uses Vite for development and building. The main components are:

- `FaderComponent` - Interactive audio faders
- `PlayButton`, `RecordButton` - Audio control buttons  
- `UndoButton`, `RedoButton` - Action history controls
- `SectionButton` - Navigation controls
- `IphoneFrame` - Main layout component

```
npm run dev
```

After a few seconds, your project should be accessible at the address
[http://localhost:5173/](http://localhost:5173/)


If you are satisfied with the result, you can finally build the project for release with:

```
npm run build
```

## Storybook

After installing, you can view your storybook by running:

```
npm run storybook
```

After a few seconds, your storybook should be accessible at the address
[http://localhost:6006/](http://localhost:6006/)

You can build your storybook for release with:

```
npm run build-storybook
```
