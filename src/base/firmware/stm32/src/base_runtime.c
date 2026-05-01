#include "base_runtime.h"

#include <ctype.h>
#include <string.h>

static size_t ascii_trimmed_len(const char *text) {
    size_t len;

    if (text == NULL) {
        return 0U;
    }

    len = strlen(text);
    while (len > 0U && isspace((unsigned char)text[len - 1U])) {
        len--;
    }

    return len;
}

static const char *skip_leading_spaces(const char *text) {
    if (text == NULL) {
        return "";
    }

    while (*text != '\0' && isspace((unsigned char)*text)) {
        text++;
    }
    return text;
}

static bool starts_with_word_case_insensitive(const char *text, const char *word) {
    size_t i;

    if (text == NULL || word == NULL) {
        return false;
    }

    if (*word == '\0') {
        return false;
    }

    for (i = 0U; word[i] != '\0'; ++i) {
        if (text[i] == '\0') {
            return false;
        }
        if ((char)tolower((unsigned char)text[i]) != (char)tolower((unsigned char)word[i])) {
            return false;
        }
    }

    return true;
}

static size_t count_alnum(const char *text) {
    size_t count = 0U;

    if (text == NULL) {
        return 0U;
    }

    while (*text != '\0') {
        if (isalnum((unsigned char)*text)) {
            count++;
        }
        text++;
    }

    return count;
}

void base_runtime_init(base_runtime_t *runtime, const base_config_t *config) {
    if (runtime == NULL || config == NULL) {
        return;
    }

    runtime->muted = config->muted;
    runtime->state = config->muted ? BASE_STATE_MUTED : BASE_STATE_IDLE;
    runtime->last_result = BASE_RESULT_EMPTY_AUDIO;
}

void base_runtime_set_mute(base_runtime_t *runtime, bool enabled) {
    if (runtime == NULL) {
        return;
    }

    runtime->muted = enabled;
    runtime->state = enabled ? BASE_STATE_MUTED : BASE_STATE_IDLE;
}

base_decision_t base_runtime_process_transcript(
    base_runtime_t *runtime,
    const base_config_t *config,
    const char *transcript
) {
    const char *trimmed;
    size_t wake_len;
    const char *command;
    size_t command_len;
    base_decision_t decision;

    decision.result = BASE_RESULT_INVALID_ARGUMENT;
    decision.should_send = false;
    decision.command_start = "";
    decision.command_len = 0U;

    if (runtime == NULL || config == NULL || config->wake_word == NULL) {
        return decision;
    }

    if (runtime->muted || config->muted) {
        runtime->state = BASE_STATE_MUTED;
        runtime->last_result = BASE_RESULT_MUTED;
        decision.result = BASE_RESULT_MUTED;
        return decision;
    }

    trimmed = skip_leading_spaces(transcript);
    if (ascii_trimmed_len(trimmed) == 0U) {
        runtime->state = BASE_STATE_IDLE;
        runtime->last_result = BASE_RESULT_EMPTY_AUDIO;
        decision.result = BASE_RESULT_EMPTY_AUDIO;
        return decision;
    }

    if (count_alnum(trimmed) < (size_t)config->min_voice_chars) {
        runtime->state = BASE_STATE_IDLE;
        runtime->last_result = BASE_RESULT_VAD_REJECTED_LOW_VOICE;
        decision.result = BASE_RESULT_VAD_REJECTED_LOW_VOICE;
        return decision;
    }

    if (!starts_with_word_case_insensitive(trimmed, config->wake_word)) {
        runtime->state = BASE_STATE_IDLE;
        runtime->last_result = BASE_RESULT_WAKE_WORD_MISSING;
        decision.result = BASE_RESULT_WAKE_WORD_MISSING;
        return decision;
    }

    wake_len = strlen(config->wake_word);
    command = trimmed + wake_len;
    command = skip_leading_spaces(command);
    command_len = ascii_trimmed_len(command);
    if (command_len == 0U) {
        runtime->state = BASE_STATE_IDLE;
        runtime->last_result = BASE_RESULT_WAKE_WORD_WITHOUT_COMMAND;
        decision.result = BASE_RESULT_WAKE_WORD_WITHOUT_COMMAND;
        return decision;
    }

    runtime->state = BASE_STATE_SENDING;
    runtime->last_result = BASE_RESULT_ACCEPTED;

    decision.result = BASE_RESULT_ACCEPTED;
    decision.should_send = true;
    decision.command_start = command;
    decision.command_len = command_len;
    return decision;
}
