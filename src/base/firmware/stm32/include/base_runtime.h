#ifndef BASE_RUNTIME_H
#define BASE_RUNTIME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BASE_STATE_IDLE = 0,
    BASE_STATE_LISTENING,
    BASE_STATE_SENDING,
    BASE_STATE_SPEAKING,
    BASE_STATE_MUTED,
    BASE_STATE_ERROR
} base_state_t;

typedef enum {
    BASE_RESULT_ACCEPTED = 0,
    BASE_RESULT_EMPTY_AUDIO,
    BASE_RESULT_VAD_REJECTED_LOW_VOICE,
    BASE_RESULT_WAKE_WORD_MISSING,
    BASE_RESULT_WAKE_WORD_WITHOUT_COMMAND,
    BASE_RESULT_MUTED,
    BASE_RESULT_INVALID_ARGUMENT
} base_result_t;

typedef struct {
    const char *wake_word;
    uint8_t min_voice_chars;
    bool muted;
} base_config_t;

typedef struct {
    base_state_t state;
    bool muted;
    base_result_t last_result;
} base_runtime_t;

typedef struct {
    base_result_t result;
    bool should_send;
    const char *command_start;
    size_t command_len;
} base_decision_t;

void base_runtime_init(base_runtime_t *runtime, const base_config_t *config);
void base_runtime_set_mute(base_runtime_t *runtime, bool enabled);
base_decision_t base_runtime_process_transcript(
    base_runtime_t *runtime,
    const base_config_t *config,
    const char *transcript
);

#ifdef __cplusplus
}
#endif

#endif
