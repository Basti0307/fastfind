# FastFind
**Fast Find is a lightweight python library that lets you search files or directories extremely fast on Windows/Linux in your code while providing high customizability.**
<br>
### Installation
Use the following command to install fastfind:
```bash
pip install fastfind
```
<br>

### Usage
Make sure to first import the library before using it in your code.

```python
import fastfind
```
<br>

Then you can search for a file/folder by using:

```python
result = fastfind.search(query="hidden_file", search_type="any", max_results=1000, timeout=5.0, roots=["C:\\Users"], all_dirs=True, max_files_per_dir=30, exact_match=True, exclude_folders=["C:\\Program_Files"], exclude_keywords=[.txt])
```
<br>

| Argument | Datatype | Explanation | Default Value |
| --- | --- | --- | --- |
| query | str | The name of the file/folder you want to search for | Required |
| roots | list[str] or None | The root directories to search, if None are provided all drives and folders will be searched | None |
| exact_match | bool | When set to True, the given query has to exactly match the file/folders name instead of just containing it | False |
| search_type | str, use: "any", "file" or "dir" | Whether you want to search only for files, folders or both | any |
| max_results | int | How many results will be returned before stopping | 1000 |
| timeout | float or int | The time in s of how long it takes before the library times out and stops searching | 5.0 |
| all_dirs | bool | If set to True, all files, including system files, will be searched that would otherwise wouldn't be searched due to better performance | False |
| max_files_per_dir | int or None | Limts how many files can be output from one single directory | None |
| exclude_folders | list[str] or None | Folders that will be excluded in the search. This is not affected by  all_dirs | None |
| exclude_keywords | list[str] or None | Excludes results that have these given keywords in them | None |

<br>

>[!NOTE]
>When you want to **include all subfolders of a folder** in "exclude_folders" or "roots" use **'/Folder/Path/.'** ! When only using **'/Folder/Path/'** no subfolders will be included and only the first layer of folders will be included/excluded when searching.
