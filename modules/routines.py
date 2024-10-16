from enum import Enum


class Routines(Enum):
    IDLE = -1
    Greeting = 0
    TaskOrientedInfo = 1
    IfSingleDescriptionCorrect = 2
    PersonalInfo = 3
    TaskSummarization = 4

    def is_finished(self, **kwargs):
        if self in [Routines.TaskOrientedInfo, Routines.PersonalInfo]:
            key_info = kwargs.get('key_info')
            missing_key = key_info.get('missing_key')
            if key_info and missing_key == []:
                return True
            return False
        elif self == Routines.IfSingleDescriptionCorrect:
            key_info = kwargs.get('key_info')
            return key_info.get('TrueOrFalse') is True
        else:
            return True

    def branch(self, **kwargs):
        if self == Routines.IfSingleDescriptionCorrect:
            is_correct = kwargs.get('is_correct', True)  # Default next is True
            if not is_correct:
                return Routines.TaskOrientedInfo
        else:
            return None

    def response_context(self, chat_handler, is_finished=False, **kwargs):
        # TODO 决定什么时候说什么
        if self == Routines.Greeting:
            response_context, is_finished = chat_handler.generate_general_response()
            return response_context

        elif self == Routines.TaskOrientedInfo:
            if not is_finished:
                response_context = chat_handler.generate_task_related_query_response(
                    missing_params=kwargs.get('missing_params'))
                return response_context
            return None
        else:
            return None

    def think(self, kie_extractor_ins, chat_history, param_dict=None):
        goto_sub_task = Routines.IDLE
        if self == Routines.IfSingleDescriptionCorrect:
            key_info, missing_key = kie_extractor_ins.classify(classify_type="TrueOrFalse",
                                                               prompt_name='if_paraphrase_correctly',
                                                               chat_input=chat_history)
            is_finished = self.is_finished(key_info=key_info,
                                           missing_key=missing_key)
            goto_sub_task = Routines.TaskOrientedInfo if not is_finished else Routines.IDLE
        elif self == Routines.TaskOrientedInfo:
            key_info, missing_key = kie_extractor_ins.extract(key_information_name=self.name,
                                                              chat_input=chat_history)
            is_finished = self.is_finished(key_info=key_info,
                                           missing_key=missing_key)
            goto_sub_task = Routines.IfSingleDescriptionCorrect if not is_finished else Routines.TaskOrientedInfo
        elif self in [Routines.PersonalInfo]:
            key_info, missing_key = kie_extractor_ins.extract(key_information_name=self.name,
                                                              chat_input=chat_history)
            is_finished = self.is_finished(key_info=key_info,
                                           missing_key=missing_key)
        else:
            key_info, missing_key, is_finished = None, None, True
        return key_info, missing_key, is_finished, goto_sub_task
