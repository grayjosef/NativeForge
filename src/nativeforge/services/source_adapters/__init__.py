"""Source-specific adapters (Gate 171).

Everything under this package is allowed to know a source's name, its URL
shape and its response format. Nothing outside it is. Gate 171Q enforces that
split by scanning the generic layers for the names that live here, so this
package is the one place a source family can be spelled out.

An adapter's whole job is: build a bounded request, and read bytes back into
records. It does not decide identity, it does not write the canonical graph,
and it does not resolve its own authorization - those are decisions the
generic layer makes ABOUT what an adapter reported.
"""
