import { FaderComponent } from ".";

export default {
  title: "Components/FaderComponent",
  component: FaderComponent,
  argTypes: {
    initialValue: {
      control: { type: 'range', min: 0, max: 1, step: 0.1 }
    },
    onChange: { action: 'changed' }
  }
};

export const Default = {
  args: {
    faderName: "Backing",
    className: {},
    initialValue: 0.5,
  },
};

export const HighValue = {
  args: {
    faderName: "Lead",
    className: {},
    initialValue: 0.8,
  },
};

export const LowValue = {
  args: {
    faderName: "Bass",
    className: {},
    initialValue: 0.2,
  },
};
