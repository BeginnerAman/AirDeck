/**
 * AirDeck AudioWorklet Processor
 * Runs on a dedicated background audio rendering thread.
 * Converts Float32 audio samples to 16-bit PCM for PyAudio / VB-Cable without UI stutter.
 */
class AirDeckMicProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input.length > 0) {
      const channelData = input[0];
      const int16 = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      // Transfer Int16 buffer with zero-copy
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}

registerProcessor("airdeck-mic-processor", AirDeckMicProcessor);
