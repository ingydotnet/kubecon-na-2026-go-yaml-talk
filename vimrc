set noshowmode
set autoread
set nohlsearch
let &statusline = substitute(&statusline, '%-20f',
      \ "%-20{expand('%:t')}", '')

silent! unmap AA
map QQ ;

" au BufRead * syn match vroom_command "\v^\s*[\$>].*$"
hi vroom_command term=bold,italic,underline ctermfg=Yellow
hi https_url term=bold,italic,underline ctermfg=LightBlue
hi vroom_emphasis term=NONE cterm=NONE ctermfg=121 gui=NONE guifg=#87ffaf
hi vroom_code term=NONE cterm=NONE ctermfg=153 gui=NONE guifg=#afd7ff
hi vroom_comment term=NONE cterm=NONE ctermfg=250 gui=NONE guifg=#bcbcbc
hi vroom_accent term=NONE cterm=NONE ctermfg=216 gui=NONE guifg=#ffaf87
hi vroom_emphasis_bold term=bold cterm=bold ctermfg=121 gui=bold guifg=#87ffaf
hi vroom_code_bold term=bold cterm=bold ctermfg=153 gui=bold guifg=#afd7ff
hi vroom_accent_bold term=bold cterm=bold ctermfg=216 gui=bold guifg=#ffaf87
hi vroom_current term=bold cterm=bold ctermfg=231 gui=bold guifg=#ffffff
hi vroom_heading term=NONE cterm=NONE ctermfg=225 gui=NONE guifg=#ffafff
hi vroom_final term=bold,underline cterm=bold,underline ctermfg=231
      \ gui=bold,underline guifg=#ffffff
hi vroom_final_url term=underline cterm=underline ctermfg=LightBlue
      \ gui=underline guifg=#35c9ff
hi vroom_bold term=bold cterm=bold gui=bold

function! VroomHighlight()
  syn match vroom_ansi /\e\[[0-9;]*m/ conceal contained
  syn cluster vroom_spans contains=vroom_emphasis,vroom_code,vroom_comment
  syn cluster vroom_spans add=vroom_accent,vroom_emphasis_bold
  syn cluster vroom_spans add=vroom_code_bold,vroom_accent_bold
  syn cluster vroom_spans add=vroom_bold
  syn match vroom_command "^\s*\%(\e\[[0-9;]*m\)*[$>].*$"
        \ contains=@vroom_spans,vroom_bold_command
  syn match https_url "\vhttps:.*"
        \ contains=@vroom_spans,vroom_ansi,vroom_bold_url
  syn region vroom_bold matchgroup=vroom_ansi
        \ start=/\e\[1m/ end=/\e\[\%(1\|22\)m/ oneline concealends
  " Plain bold spans keep their surrounding color and final underline.
  for [context, color, hex, attributes] in [
        \ ['command', 'Yellow', '#d7a900', 'bold'],
        \ ['url', 'LightBlue', '#35c9ff', 'bold'],
        \ ['heading', '225', '#ffafff', 'bold'],
        \ ['current', '231', '#ffffff', 'bold'],
        \ ['final', '231', '#ffffff', 'bold,underline'],
        \ ['final_url', 'LightBlue', '#35c9ff', 'bold,underline']]
    let group = 'vroom_bold_' . context
    execute 'highlight ' . group . ' term=' . attributes
          \ . ' cterm=' . attributes . ' ctermfg=' . color
          \ . ' gui=' . attributes . ' guifg=' . hex
    execute 'syntax region ' . group . ' matchgroup=vroom_ansi'
          \ . ' start=/\e\[1m/ end=/\e\[\%(1\|22\)m/'
          \ . ' oneline concealends contained'
  endfor
  syn region vroom_emphasis matchgroup=vroom_ansi
        \ start=/\e\[22;38;5;121m/ end=/\e\[0m/ oneline concealends
  syn region vroom_code matchgroup=vroom_ansi
        \ start=/\e\[22;38;5;153m/ end=/\e\[0m/ oneline concealends
  syn region vroom_comment matchgroup=vroom_ansi
        \ start=/\e\[22;38;5;250m/ end=/\e\[0m/ oneline concealends
  syn region vroom_accent matchgroup=vroom_ansi
        \ start=/\e\[22;38;5;216m/ end=/\e\[0m/ oneline concealends
  syn region vroom_emphasis_bold matchgroup=vroom_ansi
        \ start=/\e\[1;38;5;121m/ end=/\e\[0m/ oneline concealends
  syn region vroom_code_bold matchgroup=vroom_ansi
        \ start=/\e\[1;38;5;153m/ end=/\e\[0m/ oneline concealends
  syn region vroom_accent_bold matchgroup=vroom_ansi
        \ start=/\e\[1;38;5;216m/ end=/\e\[0m/ oneline concealends
  " Underlined spans retain their inline color on the final bullet.
  for [name, color, hex] in [
        \ ['emphasis', 121, '#87ffaf'], ['code', 153, '#afd7ff'],
        \ ['comment', 250, '#bcbcbc'], ['accent', 216, '#ffaf87']]
    for weight in (name ==# 'comment' ? [22] : [22, 1])
      let group = 'vroom_' . name . (weight == 1 ? '_bold' : '') . '_underlined'
      let attributes = weight == 1 ? 'bold,underline' : 'underline'
      execute 'highlight ' . group . ' term=' . attributes
            \ . ' cterm=' . attributes . ' ctermfg=' . color
            \ . ' gui=' . attributes . ' guifg=' . hex
      execute 'syntax cluster vroom_spans add=' . group
      execute 'syntax region ' . group . ' matchgroup=vroom_ansi'
            \ . ' start=/\e\[' . weight . ';4;38;5;' . color . 'm/'
            \ . ' end=/\e\[0m/ oneline concealends'
    endfor
  endfor
  syn match vroom_final_url /\vhttps:.*/ contained
        \ contains=@vroom_spans,vroom_ansi,vroom_bold_final_url
  silent! syn clear vroom_current
  syn match vroom_current /^\s*\e\[1;38;5;231m.*$/
        \ contains=@vroom_spans,vroom_ansi,https_url,vroom_bold_current
  silent! syn clear vroom_final
  syn match vroom_final /\e\[1;4;38;5;231m.*$/
        \ contains=@vroom_spans,vroom_ansi,vroom_final_url,vroom_bold_final
  syn match vroom_heading /^\s*\e\[22;38;5;225m.*$/
        \ contains=@vroom_spans,vroom_ansi,https_url,vroom_bold_heading
  setlocal conceallevel=2 concealcursor=nc
  if expand('%:t') =~# '^0\d\+[a-z]*\%(\.[[:alnum:]_-]\+\)*$'
    setlocal nowrap
  endif
endfunction

augroup vroom_presentation
  autocmd!
  au BufWinEnter,VimEnter * call VroomHighlight()
  au BufRead,BufNewFile *.ys,*.YS set filetype=ps1
  au BufRead,BufNewFile *.yaml set filetype=yaml
  au VimEnter * ++nested call VroomStartPresentation()
augroup END

function! VroomStartPresentation()
  if exists('g:vroom_presentation_started')
    return
  endif
  let g:vroom_presentation_started = 1
  let requested = $VROOM_START_SLIDE
  if requested != '' && requested !~# '^0\+$'
    if requested !~# '^\d\+$'
      echoerr 'Invalid starting slide: ' . requested
      cquit
    endif
    let target = -1
    for index in range(argc())
      let number = matchstr(fnamemodify(argv(index), ':t'), '^\d\+')
      if number != '' && str2nr(number) == str2nr(requested)
        let target = index
        break
      endif
    endfor
    if target < 0
      echoerr 'Starting slide not found: ' . requested
      cquit
    endif
    execute 'argument ' . (target + 1)
    normal! gg
  endif
  if $VROOM_WATCH ==# '1'
    source ./util/vroom-watch.vim
    call VroomWatchStart()
  endif
endfunction

" map j /^\(\s\+[\$>]\\|.*https:\)<cr>
" map k ?^\(\s\+[\$>]\\|.*https:\)<cr>
map j /^\(\s*\%(\e\[[0-9;]*m\)*[$>]\\|.*https:\)<cr>
map k ?^\(\s*\%(\e\[[0-9;]*m\)*[$>]\\|.*https:\)<cr>

function! VroomSlideRunner()
  if getline('.') != ''
    execute "!./vroom-slide-runner " . bufname('%') . " " . a:lastline
  endif
endfunction

map <ENTER> :call VroomSlideRunner()<CR><CR>

function! VroomNextSlide()
  let current = matchstr(expand('%:t'), '^\d\+')
  for index in range(argidx() + 1, argc() - 1)
    let slide = fnamemodify(argv(index), ':t')
    if slide =~# '^\d\+' && matchstr(slide, '^\d\+') !=# current
      execute 'argument ' . (index + 1)
      normal! gg
      return
    endif
  endfor
endfunction

nnoremap <silent> , :call VroomNextSlide()<CR>

map q ;
map qq :<cr>
map QW :q!<cr><cr>
map rr :e! %<cr>
map yy :set ft=yaml %<cr>
map 1 :wincmd o<cr>
map 2 :wincmd v<cr>
map \1 :w<cr>

call VroomHighlight()
