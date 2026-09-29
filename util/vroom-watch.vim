if exists('s:initialized')
  finish
endif
let s:initialized = 1
let s:root = getcwd()
let s:cache = s:root . '/.cache/vroom-watch'
let s:timer = -1
let s:job = v:null
let s:attempt = ''
let s:pending = {}
let s:slides = map(copy(argv()), 'fnamemodify(v:val, ":t")')

function! s:Signature()
  let source = s:root . '/slides.vroom'
  let paths = [source]
  if filereadable(source)
    for line in readfile(source)
      let include = matchlist(line, '^----\s\+include\s\+\(\S\+\)')
      if !empty(include)
        let path = include[1] =~# '^/'
              \ ? include[1] : s:root . '/' . include[1]
        call add(paths, fnamemodify(path, ':p'))
      endif
    endfor
  endif
  let contents = []
  for path in paths
    call add(contents, path)
    call add(contents, filereadable(path)
          \ ? join(readfile(path, 'b'), "\n") : '<missing>')
  endfor
  return sha256(string(contents))
endfunction

function! s:Finished(job, status)
  let s:job = v:null
  if a:status != 0
    echohl WarningMsg
    echom 'Slide rebuild failed; see .cache/vroom-watch/build.log'
    echohl None
    return
  endif
  try
    let s:pending = json_decode(join(
          \ readfile(s:cache . '/manifest.json'), "\n"))
  catch
    echohl WarningMsg
    echom 'Cannot read rebuilt slide list: ' . v:exception
    echohl None
  endtry
endfunction

function! s:SlideNumber(filename)
  return str2nr(matchstr(a:filename, '^\d\+'))
endfunction

function! s:Apply()
  let current = expand('%:t')
  if empty(s:pending) || index(s:slides, current) < 0 || &modified
        \ || mode(1) !~# '^n\|^ce$'
    return
  endif
  let number = s:SlideNumber(current)
  let old_group = filter(copy(s:slides), 's:SlideNumber(v:val) == number')
  let step = index(old_group, current)
  let slides = s:pending.slides
  let group = filter(copy(slides), 's:SlideNumber(v:val) == number')
  if empty(group)
    let preceding = filter(copy(slides), 's:SlideNumber(v:val) < number')
    let nearest = empty(preceding) ? slides[0] : preceding[-1]
    let number = s:SlideNumber(nearest)
    let group = filter(copy(slides), 's:SlideNumber(v:val) == number')
  endif
  let target = group[min([max([step, 0]), len(group) - 1])]
  let path = s:root . '/' . target
  if getbufvar(bufnr(path), '&modified')
    return
  endif
  let view = winsaveview()
  let s:slides = copy(slides)
  let s:pending = {}
  silent argdelete *
  execute 'argadd ' . join(map(copy(slides),
        \ 'fnameescape(s:root . "/" . v:val)'), ' ')
  execute 'silent keepalt argument ' . (index(slides, target) + 1)
  " Both the old and target buffers are unmodified at this point.
  silent keepalt edit!
  execute 'source ' . fnameescape(s:root . '/.vimrc')
  call winrestview(view)
  redraw
endfunction

function! s:Tick(timer)
  try
    call s:Apply()
    if s:job isnot v:null
      return
    endif
    let signature = s:Signature()
    if signature ==# s:attempt
      return
    endif
    let s:attempt = signature
    let s:job = job_start(
          \ [$VROOM_WATCH_PERL, s:root . '/util/vroom-watch-compile'], {
          \ 'cwd': s:root,
          \ 'out_io': 'file', 'out_name': s:cache . '/build.log',
          \ 'err_io': 'out', 'exit_cb': function('s:Finished')})
    if job_status(s:job) ==# 'fail'
      let s:job = v:null
      echoerr 'Cannot start the slide compiler'
    endif
  catch
    echohl WarningMsg
    echom 'Slide watcher: ' . v:exception
    echohl None
  endtry
endfunction

function! VroomWatchStop()
  call timer_stop(s:timer)
  let s:timer = -1
  if s:job isnot v:null
    call job_stop(s:job)
    let s:job = v:null
  endif
endfunction

function! VroomWatchStart()
  if s:timer != -1
    return
  endif
  if !has('timers') || !has('job') || empty($VROOM_WATCH_PERL)
    echoerr 'run-watch requires Vim timers/jobs and Makes-managed Perl'
    cquit
  endif
  call mkdir(s:cache, 'p')
  let s:timer = timer_start(1000, function('s:Tick'), {'repeat': -1})
  augroup vroom_watch
    autocmd!
    autocmd VimLeavePre * call VroomWatchStop()
  augroup END
endfunction
