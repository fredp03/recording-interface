import React from "react";
import { FaderComponent } from "../../components/FaderComponent";
import { PlayButton } from "../../components/PlayButton";
import { RedoButton } from "../../components/RedoButton";
import { SectionButton } from "../../components/SectionButton";
import { UndoButton } from "../../components/UndoButton";
import { RecordButton } from "../../icons/RecordButton";
import "./style.css";

export const IphoneFrame = () => {
  return (
    <div className="iphone-frame" data-model-id="1:359">
      <div className="frame-contents">
        <div className="section-buttons">
          <SectionButton
            button="/img/button-1.svg"
            className="section-button-instance"
          />
          <SectionButton
            button="/img/button-2.svg"
            className="section-button-instance"
          />
          <SectionButton
            button="/img/button-3.svg"
            className="section-button-instance"
          />
        </div>

        <div className="fader-section">
          <div className="spacer" />

          <FaderComponent
            className="fader-component-instance"
            initialValue={0.3}
            faderName="Backing"
          />
          <div className="spacer" />

          <FaderComponent
            className="fader-component-instance"
            initialValue={0.7}
            faderName="Me"
          />
          <div className="spacer" />
        </div>

        <div className="controls">
          <div className="playback-controls">
            <div className="spacer" />

            <PlayButton className="play-button-instance" />
            <div className="spacer" />

            <RecordButton className="record-button" />
            <div className="spacer" />
          </div>

          <div className="undo-buttons">
            <div className="spacer" />

            <UndoButton className="undo-button-instance" />
            <div className="spacer" />

            <RedoButton className="redo-button-instance" />
            <div className="spacer" />
          </div>
        </div>
      </div>
    </div>
  );
};
