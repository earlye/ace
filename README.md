# ACE Build System

So I'd like to have a build system similar to maven, but which
supports many languages.

I want it to work with multiple compilers (Clang and G++ to start
with), and I want it to generally "just work."

I want it to be emacs-friendly; when it descends into directories, it
should provide output indicating as such so that compiler error
messages are easily followed back to the source (make has stopped
doing this for some reason.)

I want it to fall back to make, maven, etc., when it descends into
directories which aren't yet ACE friendly.

