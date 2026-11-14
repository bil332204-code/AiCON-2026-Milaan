"""Child-process entry for statement PDF parsing. Reads the PDF on stdin, prints JSON.

Runs with no application secrets in its environment. Before any PDF library is imported it
caps its own address space and CPU time, and it bounds every Flate stream so a small file
cannot expand into gigabytes (a decompression bomb).
"""
import json
import sys
import zlib


def _limit_resources():
    try:
        import resource
    except ImportError:  # Windows: rely on the parent's wall-clock timeout and decode caps
        return
    from app.statement_pdf import SANDBOX_MEMORY_BYTES, SANDBOX_CPU_SECONDS
    for kind, value in ((resource.RLIMIT_AS, SANDBOX_MEMORY_BYTES), (resource.RLIMIT_CPU, SANDBOX_CPU_SECONDS),
                        (resource.RLIMIT_CORE, 0)):
        try:
            resource.setrlimit(kind, (value, value))
        except (ValueError, OSError):
            pass


class _BoundedZlib:
    """Stand-in for the zlib module inside pdfminer: same API, bounded output."""
    error = zlib.error

    def __init__(self, per_stream, total):
        self.per_stream, self.remaining = per_stream, total

    def decompress(self, data, *args, **kwargs):
        from app.statement_pdf import DecodeLimitExceeded
        engine = zlib.decompressobj()
        cap = min(self.per_stream, self.remaining)
        out = engine.decompress(data, cap + 1)
        if len(out) > cap:
            raise DecodeLimitExceeded()
        self.remaining -= len(out)
        return out

    def decompressobj(self, *args, **kwargs):
        outer, engine = self, zlib.decompressobj(*args, **kwargs)

        class Bounded:
            def decompress(self, data, max_length=0):
                from app.statement_pdf import DecodeLimitExceeded
                out = engine.decompress(data, max_length) if max_length else engine.decompress(data)
                outer.remaining -= len(out)
                if outer.remaining < 0:
                    raise DecodeLimitExceeded()
                return out

            def __getattr__(self, name):
                return getattr(engine, name)
        return Bounded()

    def __getattr__(self, name):
        return getattr(zlib, name)


def main():
    _limit_resources()
    from app.statement_pdf import (read_statement_pdf_in_process, StatementPDFError, DecodeLimitExceeded,
                                   MAX_STREAM_BYTES, MAX_DECODED_BYTES, TOO_COMPLEX)
    raw = sys.stdin.buffer.read()
    try:
        import pdfminer.pdftypes as pdftypes
        pdftypes.zlib = _BoundedZlib(MAX_STREAM_BYTES, MAX_DECODED_BYTES)
        result = {"ok": True, "result": read_statement_pdf_in_process(raw)}
    except StatementPDFError as exc:
        result = {"ok": False, "error": str(exc)}
    except (MemoryError, DecodeLimitExceeded, RecursionError):
        result = {"ok": False, "error": TOO_COMPLEX}
    except Exception:  # never leak parser internals to the seller
        result = {"ok": False, "error": "This PDF could not be read. Try downloading it again from your bank or wallet app."}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
