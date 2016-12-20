// $automatically_generated
#include <iostream>
#include <typeinfo>

$test_declarations

typedef void (*test_fn)();
struct test
{
  test_fn fn_;
  char const* name_;
};

test tests[] = {
  $test_list
};

int main(int argc, char**argv)
{
  int fail_count = 0;
  int pass_count = 0;
  std::cerr.copyfmt(std::cout);
  std::cerr.clear(std::cout.rdstate());
  std::cerr.rdbuf(std::cout.rdbuf());
  std::clog.copyfmt(std::cout);
  std::clog.clear(std::cout.rdstate());
  std::clog.rdbuf(std::cout.rdbuf());
  for( auto current_test : tests )
    {
      std::cout << "--- \"" << current_test.name_ << "\"" << std::endl;
      try
        {
          current_test.fn_();
          std::cout << "test \"" << current_test.name_ << "\" PASSED" << std::endl;
          ++pass_count;
        }
      catch( std::exception& e )
        {
          std::cerr << "test \"" << current_test.name_ << "\" FAILED:\n" << typeid(e).name() << ":" << e.what() << std::endl;
          ++fail_count;
        }
      catch( ... )
        {
          std::cerr << "test \"" << current_test.name_ << "\" FAILED:\n" << std::endl;
          ++fail_count;
        }
    }
  std::cout << pass_count << " tests PASSED" << std::endl;
  std::cout << fail_count << " tests FAILED" << std::endl;
  return fail_count != 0;
};
