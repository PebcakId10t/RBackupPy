import argparse
import textwrap

class SmartHelpFormatter(argparse.HelpFormatter):
    """Sane formatting of paragraphs in program description, courtesty of:
    https://stackoverflow.com/questions/3853722/how-to-insert-newlines-on-argparse-help-text
    Thanks to user flaz14 for posting
    """

    def _fill_text(self, text, width, indent):
        text = self._whitespace_matcher.sub(" ", text).strip()
        paragraphs = text.split("|n ")
        output = ""
        for para in paragraphs:
            formatted_para = (
                textwrap.fill(
                    para, width, initial_indent=indent, subsequent_indent=indent
                )
                + "\n\n"
            )
            output += formatted_para
        return output


class SmartArgumentDefaultsHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter, SmartHelpFormatter
):
    pass
