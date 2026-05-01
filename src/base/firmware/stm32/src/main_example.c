#include "base_runtime.h"

#include <stdio.h>

int main(void) {
    base_config_t config;
    base_runtime_t runtime;
    base_decision_t decision;

    config.wake_word = "nova";
    config.min_voice_chars = 6U;
    config.muted = false;

    base_runtime_init(&runtime, &config);
    decision = base_runtime_process_transcript(&runtime, &config, "nova allume la lumiere");

    printf("result=%d should_send=%d command_len=%zu\n",
           (int)decision.result,
           decision.should_send ? 1 : 0,
           decision.command_len);

    return decision.should_send ? 0 : 1;
}
