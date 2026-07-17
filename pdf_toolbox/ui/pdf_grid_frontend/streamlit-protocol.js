"use strict";

const StreamlitProtocol = {
  send(type, data) {
    window.parent.postMessage(
      Object.assign({ isStreamlitMessage: true, type }, data),
      "*"
    );
  },

  ready() {
    this.send("streamlit:componentReady", { apiVersion: 1 });
  },

  setFrameHeight(height) {
    this.send("streamlit:setFrameHeight", { height });
  },

  setComponentValue(value) {
    this.send("streamlit:setComponentValue", {
      value,
      dataType: "json",
    });
  },

  onRender(callback) {
    window.addEventListener("message", (event) => {
      if (!event.data || event.data.type !== "streamlit:render") return;
      callback(event.data.args || {});
    });
  },
};
