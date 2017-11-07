// $automatically_generated
#include <ace/run_test.hpp>
#include <iostream>
#include <typeinfo>

$test_declarations

ace::test tests[] = {
  $test_list
};


int main(int argc, char**argv)
{
  std::cerr.copyfmt(std::cout);
  std::cerr.clear(std::cout.rdstate());
  std::cerr.rdbuf(std::cout.rdbuf());
  std::clog.copyfmt(std::cout);
  std::clog.clear(std::cout.rdstate());
  std::clog.rdbuf(std::cout.rdbuf());
  ace::stats statistics = {0};
  for( auto current_test : tests )
    {
      ace::run_test(current_test, statistics);
    }
  std::cout << statistics.pass_count << " tests PASSED" << std::endl;
  std::cout << statistics.fail_count << " tests FAILED" << std::endl;
  return statistics.fail_count != 0;
};
