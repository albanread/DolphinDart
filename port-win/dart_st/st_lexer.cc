// MACVM Smalltalk (.mst) reader — tokenizer implementation.

#include "st_lexer.h"

#include <cctype>
#include <string>

namespace st {

bool IsIdentStart(int c) {
  return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_';
}

bool IsIdentCont(int c) {
  return IsIdentStart(c) || (c >= '0' && c <= '9');
}

bool IsBinaryChar(int c) {
  switch (c) {
    case '+': case '-': case '*': case '/': case '~': case '<': case '>':
    case '=': case '&': case '|': case '@': case '%': case ',': case '?':
    case '!': case '\\':
      return true;
    default:
      return false;
  }
}

Lexer::Lexer(std::string src) : src_(std::move(src)) {}

bool Lexer::AtEnd() const { return idx_ >= src_.size(); }

int Lexer::Peek(int ahead) const {
  size_t p = idx_ + static_cast<size_t>(ahead);
  if (p >= src_.size()) return -1;
  return static_cast<unsigned char>(src_[p]);
}

int Lexer::Advance() {
  if (AtEnd()) return -1;
  int c = static_cast<unsigned char>(src_[idx_++]);
  if (c == '\n') {
    line_++;
    col_ = 1;
  } else {
    col_++;
  }
  return c;
}

// Skips runs of whitespace and "double-quoted" comments. Comments may contain
// "" as an escaped quote. Sets *error if a comment is unterminated.
void Lexer::SkipWhitespaceAndComments(bool* error, LexError* err) {
  for (;;) {
    int c = Peek();
    if (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\f' ||
        c == '\v') {
      Advance();
      continue;
    }
    if (c == '"') {
      int start_line = line_, start_col = col_;
      Advance();  // opening quote
      for (;;) {
        int d = Peek();
        if (d == -1) {
          *error = true;
          err->line = start_line;
          err->col = start_col;
          err->message = "unterminated comment";
          return;
        }
        if (d == '"') {
          if (Peek(1) == '"') {  // "" escaped quote inside comment
            Advance();
            Advance();
            continue;
          }
          Advance();  // closing quote
          break;
        }
        Advance();
      }
      continue;
    }
    return;
  }
}

// Reads a number. Handles: leading '-' (already consumed by caller decision),
// radix integers `16rFF`, floats `1.5` / `1.0e3` / `1e10`. Returns a kInt or
// kFloat token. The caller passes the starting line/col via member state.
Token Lexer::MakeNumber(bool* error, LexError* err) {
  (void)error;
  (void)err;
  Token t;
  t.line = line_;
  t.col = col_;
  std::string s;

  if (Peek() == '-') s += static_cast<char>(Advance());

  // Integer part.
  while (std::isdigit(Peek())) s += static_cast<char>(Advance());

  // Radix integer: <digits> 'r' <radix-digits>.
  if (Peek() == 'r') {
    s += static_cast<char>(Advance());  // 'r'
    // Radix digits may be 0-9 A-Z (and a leading '-' for signed radix).
    if (Peek() == '-') s += static_cast<char>(Advance());
    while (std::isalnum(Peek())) s += static_cast<char>(Advance());
    t.kind = Tok::kInt;
    t.text = s;
    return t;
  }

  bool is_float = false;
  // Fraction: only if a digit follows the '.', so that `3.` stays an int
  // followed by a statement separator.
  if (Peek() == '.' && std::isdigit(Peek(1))) {
    is_float = true;
    s += static_cast<char>(Advance());  // '.'
    while (std::isdigit(Peek())) s += static_cast<char>(Advance());
  }

  // Exponent.
  if (Peek() == 'e' || Peek() == 'E' || Peek() == 'd' || Peek() == 'D') {
    int nxt = Peek(1);
    bool signed_exp = (nxt == '+' || nxt == '-');
    int after = signed_exp ? Peek(2) : nxt;
    if (std::isdigit(after)) {
      is_float = true;
      s += static_cast<char>(Advance());  // e/E/d/D
      if (signed_exp) s += static_cast<char>(Advance());
      while (std::isdigit(Peek())) s += static_cast<char>(Advance());
    }
  }

  t.kind = is_float ? Tok::kFloat : Tok::kInt;
  t.text = s;
  return t;
}

// Reads a single-quoted string. '' is an escaped quote. The opening quote is at
// the current position.
Token Lexer::MakeString(bool* error, LexError* err) {
  Token t;
  t.kind = Tok::kString;
  t.line = line_;
  t.col = col_;
  int start_line = line_, start_col = col_;
  Advance();  // opening '
  std::string s;
  for (;;) {
    int c = Peek();
    if (c == -1) {
      *error = true;
      err->line = start_line;
      err->col = start_col;
      err->message = "unterminated string literal";
      break;
    }
    if (c == '\'') {
      if (Peek(1) == '\'') {  // '' escaped quote
        Advance();
        Advance();
        s += '\'';
        continue;
      }
      Advance();  // closing '
      break;
    }
    s += static_cast<char>(Advance());
  }
  t.text = s;
  return t;
}

// Reads a symbol token starting at '#'. Forms:
//   #foo #foo:bar:  (keyword-run)  #+  (binary)  #'quoted symbol'
// Also detects the array/byte-array introducers #( and #[ which are returned
// as distinct tokens for the parser to handle.
Token Lexer::MakeSymbol(bool* error, LexError* err) {
  Token t;
  t.line = line_;
  t.col = col_;
  Advance();  // '#'

  int c = Peek();
  if (c == '(') {
    Advance();
    t.kind = Tok::kSymbolArray;
    t.text = "#(";
    return t;
  }
  if (c == '[') {
    Advance();
    t.kind = Tok::kByteArrayL;
    t.text = "#[";
    return t;
  }
  if (c == '\'') {  // quoted symbol reuses string scanning
    Token s = MakeString(error, err);
    t.kind = Tok::kSymbol;
    t.text = s.text;
    return t;
  }

  std::string s;
  if (IsIdentStart(c)) {
    // Unary or keyword-run symbol: ident (':' ident?)*  or  ident ':' ...
    while (IsIdentCont(Peek())) s += static_cast<char>(Advance());
    while (Peek() == ':') {
      s += static_cast<char>(Advance());
      while (IsIdentCont(Peek())) s += static_cast<char>(Advance());
    }
  } else if (IsBinaryChar(c)) {
    while (IsBinaryChar(Peek())) s += static_cast<char>(Advance());
  } else {
    // A lone '#' with nothing meaningful after it — treat as empty symbol.
  }
  t.kind = Tok::kSymbol;
  t.text = s;
  return t;
}

// Appends `cp` to `s` as UTF-8.
static void AppendUtf8(std::string* s, uint32_t cp) {
  if (cp < 0x80) {
    *s += static_cast<char>(cp);
  } else if (cp < 0x800) {
    *s += static_cast<char>(0xC0 | (cp >> 6));
    *s += static_cast<char>(0x80 | (cp & 0x3F));
  } else if (cp < 0x10000) {
    *s += static_cast<char>(0xE0 | (cp >> 12));
    *s += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
    *s += static_cast<char>(0x80 | (cp & 0x3F));
  } else {
    *s += static_cast<char>(0xF0 | (cp >> 18));
    *s += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
    *s += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
    *s += static_cast<char>(0x80 | (cp & 0x3F));
  }
}

// Reads a `$x` character literal.
//
// Dolphin 8 added ESCAPED character literals, and the corpus uses them:
// `$\0` for NUL, `$\n`, `$\r`, `$\t`, and `$\x<hex>` for a code point.
// `UI.TextEdit>>cueBanner` compares `buf first ~~ $\0`, and reading that as
// `$\` followed by the integer 0 left two primaries in a block — a parse
// error whose column pointed at the digit.
//
// An UNRECOGNISED escape answers the backslash itself, which is what this
// lexer did for every escape before: `$\` is a legitimate character literal,
// and the corpus contains `$\ ` (backslash) meaning exactly that.
Token Lexer::MakeCharOrDollar() {
  Token t;
  t.kind = Tok::kChar;
  t.line = line_;
  t.col = col_;
  Advance();  // '$'
  int c = Peek();
  if (c == -1) {
    t.text = "";
    return t;
  }
  if (c != '\\') {
    t.text = std::string(1, static_cast<char>(Advance()));
    return t;
  }
  // A backslash: look at what follows before committing to an escape.
  int e = Peek(1);
  switch (e) {
    case '0': Advance(); Advance(); t.text = std::string(1, '\0'); return t;
    case 'a': Advance(); Advance(); t.text = "\a"; return t;
    case 'b': Advance(); Advance(); t.text = "\b"; return t;
    case 'f': Advance(); Advance(); t.text = "\f"; return t;
    case 'n': Advance(); Advance(); t.text = "\n"; return t;
    case 'r': Advance(); Advance(); t.text = "\r"; return t;
    case 't': Advance(); Advance(); t.text = "\t"; return t;
    case 'v': Advance(); Advance(); t.text = "\v"; return t;
    case '\\': Advance(); Advance(); t.text = "\\"; return t;
    case 'x': case 'X': {
      // `$\x41` — hex digits, however many follow.
      int n = 2;
      uint32_t cp = 0;
      bool any = false;
      while (true) {
        int d = Peek(n);
        int v;
        if (d >= '0' && d <= '9') v = d - '0';
        else if (d >= 'a' && d <= 'f') v = d - 'a' + 10;
        else if (d >= 'A' && d <= 'F') v = d - 'A' + 10;
        else break;
        cp = cp * 16 + static_cast<uint32_t>(v);
        any = true;
        n++;
      }
      if (!any) break;  // `$\x` with no digits — fall through to the default
      for (int i = 0; i < n; i++) Advance();
      t.text.clear();
      AppendUtf8(&t.text, cp);
      return t;
    }
    default:
      break;
  }
  // Not an escape we know: the character IS the backslash.
  t.text = std::string(1, static_cast<char>(Advance()));
  return t;
}

// Reads an identifier or keyword (identifier immediately followed by ':').
Token Lexer::MakeIdentOrKeyword() {
  Token t;
  t.line = line_;
  t.col = col_;
  std::string s;
  while (IsIdentCont(Peek())) s += static_cast<char>(Advance());
  // Keyword: a ':' directly after the identifier, but NOT ':=' (assignment).
  if (Peek() == ':' && Peek(1) != '=') {
    s += static_cast<char>(Advance());
    t.kind = Tok::kKeyword;
  } else {
    t.kind = Tok::kIdent;
  }
  t.text = s;
  return t;
}

// Reads a run of binary-selector characters as one binary token.
Token Lexer::MakeBinary() {
  Token t;
  t.kind = Tok::kBinary;
  t.line = line_;
  t.col = col_;
  std::string s;
  while (IsBinaryChar(Peek())) s += static_cast<char>(Advance());
  t.text = s;
  return t;
}

bool Lexer::Tokenize(std::vector<Token>* tokens, LexError* err) {
  for (;;) {
    bool error = false;
    SkipWhitespaceAndComments(&error, err);
    if (error) return false;

    if (AtEnd()) {
      Token eof;
      eof.kind = Tok::kEof;
      eof.line = line_;
      eof.col = col_;
      tokens->push_back(eof);
      return true;
    }

    int c = Peek();
    int line = line_, col = col_;
    int off = static_cast<int>(idx_);   // token start offset (debug info)

    // Numbers, and the classic negative-literal-vs-binary-minus
    // disambiguation.
    //
    // A digit after '-' is NOT enough. `anInteger-1` has one, and reading
    // `-1` as a literal there leaves two primaries side by side —
    // `anInteger` `-1` — which is a parse error at a column that points at
    // the digit and explains nothing. `UI.TextEdit>>caretPosition:` is
    // `self selectionStart: anInteger end: anInteger-1`, and it took the
    // whole class file down at load.
    //
    // The rule is about what comes BEFORE: a '-' that follows something which
    // can END a primary is a binary selector, because two primaries cannot be
    // adjacent. After a keyword, an assignment, an operator or an opening
    // bracket there is no preceding primary, so the '-' is a sign.
    //
    //     foo: -1        sign     (previous token is a keyword)
    //     x := -1        sign     (previous is :=)
    //     3 + -1         sign     (previous is a binary selector)
    //     anInteger-1    binary   (previous is an identifier)
    //     (a + b)-1      binary   (previous is `)`)
    //     #(1 2)-1       binary   (previous is `)`)
    // ...EXCEPT inside a literal array, where there are no binary sends at
    // all: `#(1 2 -3)` is three integers, and the previous token is an
    // integer. Getting this wrong is worse than a parse error — the parser
    // turns a kBinary inside a literal array into a SYMBOL, so the array
    // would have become `#(1 2 #- 3)`: four elements, no diagnostic.
    //
    // Determined by walking back rather than by keeping a counter, because
    // tokens are appended from a dozen places in this loop and a counter
    // maintained in only some of them is a bug waiting to happen. The walk
    // runs only in the genuinely ambiguous case — a '-' with a digit after it
    // and a primary before it.
    //
    // A bare '(' is not a decision: inside a literal array it opens a NESTED
    // array, so the walk keeps going and lets an enclosing token decide. A
    // '[' or '{' is a decision — neither can occur inside a literal array.
    auto inside_literal_array = [&]() -> bool {
      int depth = 0;
      for (int i = static_cast<int>(tokens->size()) - 1; i >= 0; i--) {
        switch ((*tokens)[i].kind) {
          case Tok::kRParen: case Tok::kRBracket: case Tok::kRBrace:
            depth++;
            break;
          case Tok::kLBracket: case Tok::kLBrace:
            if (depth == 0) return false;
            depth--;
            break;
          case Tok::kLParen:
            if (depth > 0) depth--;
            break;
          case Tok::kSymbolArray: case Tok::kByteArrayL:
            if (depth == 0) return true;
            depth--;
            break;
          default:
            break;
        }
      }
      return false;
    };

    bool minus_is_sign = true;
    if (c == '-' && !tokens->empty() && std::isdigit(Peek(1)) &&
        !inside_literal_array()) {
      switch (tokens->back().kind) {
        case Tok::kIdent:
        case Tok::kInt:
        case Tok::kFloat:
        case Tok::kString:
        case Tok::kSymbol:
        case Tok::kChar:
        case Tok::kRParen:
        case Tok::kRBracket:
        case Tok::kRBrace:
          minus_is_sign = false;
          break;
        default:
          break;
      }
    }
    if (std::isdigit(c) ||
        (c == '-' && minus_is_sign && std::isdigit(Peek(1)))) {
      bool nerr = false;
      Token t = MakeNumber(&nerr, err);
      if (nerr) return false;
      t.offset = off;
      tokens->push_back(t);
      continue;
    }

    if (c == '\'') {
      bool serr = false;
      Token t = MakeString(&serr, err);
      if (serr) return false;
      t.offset = off;
      tokens->push_back(t);
      continue;
    }

    if (c == '#') {
      bool yerr = false;
      Token t = MakeSymbol(&yerr, err);
      if (yerr) return false;
      t.offset = off;
      tokens->push_back(t);
      continue;
    }

    if (c == '$') {
      Token t = MakeCharOrDollar();
      t.offset = off;
      tokens->push_back(t);
      continue;
    }

    if (IsIdentStart(c)) {
      Token t = MakeIdentOrKeyword();
      t.offset = off;
      tokens->push_back(t);
      continue;
    }

    // Assignment ':=' vs a bare ':' (block-argument introducer, e.g. `:x`).
    if (c == ':') {
      Advance();  // ':'
      Token t;
      t.line = line;
      t.col = col;
      t.offset = off;
      if (Peek() == '=') {
        Advance();
        t.kind = Tok::kAssign;
        t.text = ":=";
      } else {
        t.kind = Tok::kColon;
        t.text = ":";
      }
      tokens->push_back(t);
      continue;
    }

    // Single-char structural tokens.
    auto push1 = [&](Tok k, const char* txt) {
      Advance();
      Token t;
      t.kind = k;
      t.text = txt;
      t.line = line;
      t.col = col;
      t.offset = off;
      tokens->push_back(t);
    };

    switch (c) {
      case '^': push1(Tok::kCaret, "^"); continue;
      case '.': push1(Tok::kDot, "."); continue;
      case ';': push1(Tok::kSemi, ";"); continue;
      case '(': push1(Tok::kLParen, "("); continue;
      case ')': push1(Tok::kRParen, ")"); continue;
      case '[': push1(Tok::kLBracket, "["); continue;
      case ']': push1(Tok::kRBracket, "]"); continue;
      case '{': push1(Tok::kLBrace, "{"); continue;
      case '}': push1(Tok::kRBrace, "}"); continue;
      default:
        break;
    }

    // A lone '|' is emitted as kBar; a run like '||' or '|foo' where more
    // binary chars follow becomes a binary selector. We special-case the
    // single bar because the parser must disambiguate it (temps/block-args
    // terminator vs. the binary operator).
    if (c == '|') {
      if (IsBinaryChar(Peek(1))) {
        Token t = MakeBinary(); t.offset = off; tokens->push_back(t);
      } else {
        push1(Tok::kBar, "|");
      }
      continue;
    }

    if (IsBinaryChar(c)) {
      Token t = MakeBinary(); t.offset = off; tokens->push_back(t);
      continue;
    }

    // Anything else is a lexical error.
    err->line = line_;
    err->col = col_;
    err->message = std::string("unexpected character '") +
                   static_cast<char>(c) + "'";
    return false;
  }
}

}  // namespace st
